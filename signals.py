"""Build at most one informational signal per symbol from completed bars and a listed contract.

Returns (signal | None, reasons). `reasons` explains every rejection so a run can be audited.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from contracts import select_contract
from market_data import ET, aggregate_intraday, completed_history, is_fresh
from strategy import BEAR, BULL, failed_2u, fvg_retest, ftfc_direction, two_one_two

WEIGHTS = {"2-1-2": 2, "fvg_retest": 2, "failed_2u": 1, "ftfc": 2}


def generate_signal(symbol: str, client, sessions: dict, now: datetime, *, min_score: int = 4,
                    data_delay: timedelta = timedelta(0), contract_rules: dict | None = None):
    reasons: list[str] = []
    now = now.astimezone(ET)
    start = (now - timedelta(days=30)).strftime("%Y-%m-%d 09:30")
    rows = client.timesales(symbol, "15min", start, now.strftime("%Y-%m-%d %H:%M"))
    base = aggregate_intraday(rows, 15, sessions, now, data_delay)
    if not is_fresh(base, 15, now, data_delay):
        return None, ["stale_or_missing_intraday_data"]

    daily = completed_history(client.history(symbol, "daily", (now - timedelta(days=180)).date().isoformat(),
                                             now.date().isoformat()), "daily", now, sessions)
    weekly = completed_history(client.history(symbol, "weekly", (now - timedelta(days=730)).date().isoformat(),
                                              now.date().isoformat()), "weekly", now, sessions)
    bars = {
        "120": aggregate_intraday(rows, 120, sessions, now, data_delay),
        "240": aggregate_intraday(rows, 240, sessions, now, data_delay),
        "D": daily,
        "W": weekly,
    }
    if any(len(v) < 4 for v in bars.values()):
        return None, ["insufficient_completed_bars:" + ",".join(k for k, v in bars.items() if len(v) < 4)]

    trend = ftfc_direction(bars)
    if trend is None:
        return None, ["no_full_timeframe_continuity"]

    found = {}
    if (d := two_one_two(bars["240"])) is not None:
        found["2-1-2"] = d
    if (d := failed_2u(bars["240"])) is not None:
        found["failed_2u"] = d
    if (d := fvg_retest(bars["D"])) is not None:
        found["fvg_retest"] = d
    if not found:
        return None, ["no_setup"]
    if any(d != trend for d in found.values()):
        return None, ["setup_conflicts_with_continuity:" + ",".join(f"{k}={v}" for k, v in found.items())]

    score = WEIGHTS["ftfc"] + sum(WEIGHTS[k] for k in found)
    if score < min_score:
        return None, [f"score_below_minimum:{score}<{min_score}"]

    quote = client.quotes([symbol]).get(symbol) or {}
    price = quote.get("last")
    if not price:
        return None, ["no_underlying_quote"]

    contract = select_contract(trend, price, now.date(), client.option_expirations(symbol),
                               lambda e: client.option_chain(symbol, e), **(contract_rules or {}))
    if contract is None:
        return None, ["no_listed_contract_meets_liquidity_rules"]

    setup_bar = bars["240"][-1]["end"]
    signal = {
        "symbol": symbol,
        "direction": "Call" if trend == BULL else "Put",
        "trend": trend,
        "score": score,
        "setups": sorted(found),
        "underlying": round(price, 2),
        "contract": contract,
        "setup_bar_end": setup_bar.isoformat(),
        "generated_at": now.isoformat(),
        # Deduplicate on what the signal is about, not when it was computed.
        "dedupe_key": f"{symbol}|{trend}|{setup_bar.isoformat()}|{contract['option_symbol']}",
    }
    reasons.append("signal")
    return signal, reasons


__all__ = ["generate_signal", "BULL", "BEAR"]
