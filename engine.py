"""One signal cycle, independent of Discord so it can be tested deterministically.

Paper/read-only: produces informational text only. Nothing here places or simulates orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from market_data import ET, sessions_from_calendar
from policy import effective_watchlist, in_entry_window
from signals import generate_signal

DISCLAIMER = ("Informational only, not investment advice or a recommendation to buy or sell. "
              "No orders are placed by this bot. Options can lose 100% of their value.")


@dataclass
class CycleState:
    day: date | None = None
    sent_today: int = 0
    sent_keys: set = field(default_factory=set)
    bias_warned: bool = False


@dataclass
class EngineConfig:
    watchlist: list
    max_per_cycle: int = 3   # caps only; the bot never tries to reach a number of ideas
    max_per_day: int = 6
    data_delay: timedelta = timedelta(0)
    contract_rules: dict = field(default_factory=dict)


def index_bias(client) -> str:
    quotes = client.quotes(["SPY", "QQQ"])
    moves = []
    for symbol in ("SPY", "QQQ"):
        q = quotes.get(symbol) or {}
        if not q.get("last") or not q.get("open"):
            return "unknown"
        moves.append(q["last"] > q["open"])
    return "bullish" if all(moves) else "bearish" if not any(moves) else "neutral"


def load_sessions(client, now: datetime) -> dict:
    local = now.astimezone(ET)
    days = []
    # A 30-day window can cross three calendar months (for example March 2).
    # Visit each intersecting month; sampling a fixed offset can skip February.
    ref = (local - timedelta(days=30)).date().replace(day=1)
    last_month = local.date().replace(day=1)
    while ref <= last_month:
        days += client.calendar(ref.year, ref.month)
        ref = (ref.replace(day=28) + timedelta(days=4)).replace(day=1)
    return sessions_from_calendar(days)


def run_cycle(client, cfg: EngineConfig, state: CycleState, now: datetime) -> dict:
    """Returns {'messages': [...], 'skipped': {symbol: reasons}, 'market': state}."""
    local = now.astimezone(ET)
    if not in_entry_window(local.time()):
        return {"messages": [], "skipped": {}, "market": "outside_entry_window"}
    clock = client.clock()
    if clock.get("state") != "open":
        return {"messages": [], "skipped": {}, "market": clock.get("state", "unknown")}
    watchlist, rejected = effective_watchlist(cfg.watchlist)
    if state.day != local.date():
        state.day, state.sent_today, state.bias_warned = local.date(), 0, False
        state.sent_keys = {k for k in state.sent_keys if k.split("|")[2] == local.date().isoformat()}

    messages, skipped = [], {s: ["symbol_not_in_policy"] for s in rejected}
    bias = index_bias(client)
    if bias == "bearish" and not state.bias_warned:
        messages.append("Market check: SPY and QQQ are both below today's open. Signals may be less reliable.")
        state.bias_warned = True

    sessions = load_sessions(client, local)
    candidates = []
    for symbol in watchlist:
        signal, reasons = generate_signal(symbol, client, sessions, local,
                                          data_delay=cfg.data_delay, contract_rules=cfg.contract_rules)
        if signal is None:
            skipped[symbol] = reasons
        elif signal["dedupe_key"] in state.sent_keys:
            skipped[symbol] = ["duplicate_of_already_sent_signal"]
        else:
            candidates.append(signal)

    candidates.sort(key=lambda s: s["symbol"])
    room = max(0, min(cfg.max_per_cycle, cfg.max_per_day - state.sent_today))
    for signal in candidates[:room]:
        messages.append(format_signal(signal))
        state.sent_keys.add(signal["dedupe_key"])
        state.sent_today += 1
    for signal in candidates[room:]:
        skipped[signal["symbol"]] = ["signal_limit_reached"]
    return {"messages": messages, "skipped": skipped, "market": "open"}


def format_signal(s: dict) -> str:
    c, orb = s["contract"], s["opening_range"]
    return (
        f"**[{s['symbol']}] {s['direction']} idea** | ICT + Strat ({', '.join(s['strat_setups'])}) + 15m ORB, {s['trend']}\n"
        f"Underlying: {s['underlying']} | Opening range {orb['low']}-{orb['high']}\n"
        f"Listed contract: {c['option_symbol']} | {c['strike']} {c['option_type']} exp {c['expiration']} ({c['dte']} DTE)\n"
        f"Size: {c['contracts']} contract | bid {c['bid']} / ask {c['ask']} | max premium ${c['max_premium_usd']:.2f} | OI {c['open_interest']}\n"
        f"Signal bar closed: {s['signal_bar_end']}\n"
        f"_{DISCLAIMER}_"
    )
