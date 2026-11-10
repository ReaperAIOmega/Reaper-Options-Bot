"""One informational idea per symbol, only when ICT, The Strat and the 15-minute ORB independently agree.

Returns (signal | None, reasons). `reasons` explains every rejection so a run can be audited.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from contracts import select_contract
from market_data import ET, aggregate_intraday, completed_history, is_fresh
from policy import ALLOWED_SYMBOLS, REQUIRED_QUALIFICATIONS, in_entry_window
from strategy import BULL, failed_2u, ftfc_direction, ict_fvg_retest, orb_direction, two_one_two


def strat_direction(bars: dict) -> tuple[str | None, list[str]]:
    trend = ftfc_direction(bars)
    if trend is None:
        return None, ["no_full_timeframe_continuity"]
    setups = {k: d for k, d in (("2-1-2", two_one_two(bars["240"])), ("failed_2u", failed_2u(bars["240"]))) if d}
    if not setups:
        return None, ["no_strat_setup"]
    if any(d != trend for d in setups.values()):
        return None, ["strat_setup_conflicts_with_continuity"]
    return trend, sorted(setups)


def generate_signal(symbol: str, client, sessions: dict, now: datetime, *,
                    data_delay: timedelta = timedelta(0), contract_rules: dict | None = None):
    now = now.astimezone(ET)
    if symbol not in ALLOWED_SYMBOLS:
        return None, ["symbol_not_in_policy"]
    if not in_entry_window(now.time()):
        return None, ["outside_entry_window"]
    session = sessions.get(now.date())
    if session is None:
        return None, ["market_closed_today"]

    start = (now - timedelta(days=30)).strftime("%Y-%m-%d 09:30")
    rows = client.timesales(symbol, "15min", start, now.strftime("%Y-%m-%d %H:%M"))
    base = aggregate_intraday(rows, 15, sessions, now, data_delay)
    if not is_fresh(base, 15, now, data_delay):
        return None, ["stale_or_missing_intraday_data"]
    today = [b for b in base if b["start"].date() == now.date()]
    opening = today[0] if today and today[0]["start"] == session.open else None
    if opening is None or len(today) < 2:
        return None, ["opening_range_incomplete"]

    daily = completed_history(client.history(symbol, "daily", (now - timedelta(days=180)).date().isoformat(),
                                             now.date().isoformat()), "daily", now, sessions)
    weekly = completed_history(client.history(symbol, "weekly", (now - timedelta(days=730)).date().isoformat(),
                                              now.date().isoformat()), "weekly", now, sessions)
    bars = {"120": aggregate_intraday(rows, 120, sessions, now, data_delay),
            "240": aggregate_intraday(rows, 240, sessions, now, data_delay), "D": daily, "W": weekly}
    if any(len(v) < 4 for v in bars.values()):
        return None, ["insufficient_completed_bars:" + ",".join(k for k, v in bars.items() if len(v) < 4)]

    strat, strat_detail = strat_direction(bars)
    qualifications = {"strat": strat, "ict": ict_fvg_retest(base), "orb15": orb_direction(opening, base[-1])}
    missing = [k for k in REQUIRED_QUALIFICATIONS if qualifications[k] is None]
    if missing:
        detail = strat_detail if strat is None else []
        return None, ["missing_qualification:" + ",".join(missing)] + detail
    if len(set(qualifications.values())) != 1:
        return None, ["qualifications_disagree:" + ",".join(f"{k}={v}" for k, v in sorted(qualifications.items()))]
    trend = strat

    price = (client.quotes([symbol]).get(symbol) or {}).get("last")
    if not price:
        return None, ["no_underlying_quote"]
    contract = select_contract(trend, price, now.date(), client.option_expirations(symbol),
                               lambda e: client.option_chain(symbol, e), **(contract_rules or {}))
    if contract is None:
        return None, ["no_listed_contract_within_policy"]

    return {
        "symbol": symbol, "direction": "Call" if trend == BULL else "Put", "trend": trend,
        "qualifications": sorted(REQUIRED_QUALIFICATIONS), "strat_setups": strat_detail,
        "opening_range": {"high": opening["high"], "low": opening["low"]},
        "underlying": round(price, 2), "contract": contract,
        "signal_bar_end": base[-1]["end"].isoformat(), "generated_at": now.isoformat(),
        # At most one idea per symbol and direction per session.
        "dedupe_key": f"{symbol}|{trend}|{now.date().isoformat()}",
    }, ["signal"]
