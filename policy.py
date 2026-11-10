"""Owner trading policy. These are hard limits: configuration may tighten them, never loosen them.

Informational only. The bot suggests at most one contract per idea and never places orders.
"""
from datetime import time

ALLOWED_SYMBOLS = ("SPY", "QQQ", "IWM")
CONTRACTS_PER_IDEA = 1
MIN_DTE, MAX_DTE = 1, 7
MAX_PREMIUM_USD = 200.0          # worst case: ask x 100 x contracts
OPTION_MULTIPLIER = 100
ENTRY_START = time(9, 45)        # ET, inclusive
ENTRY_CUTOFF = time(15, 0)       # ET, exclusive
REQUIRED_QUALIFICATIONS = ("ict", "strat", "orb15")


def effective_watchlist(requested):
    """Only policy symbols; unknown requests are reported, not silently added."""
    requested = [s.strip().upper() for s in requested if s.strip()]
    if not requested:
        return list(ALLOWED_SYMBOLS), []
    return [s for s in requested if s in ALLOWED_SYMBOLS], [s for s in requested if s not in ALLOWED_SYMBOLS]


def contract_rules(min_open_interest=100, max_spread_pct=0.15, max_premium_usd=MAX_PREMIUM_USD, min_dte=MIN_DTE, max_dte=MAX_DTE):
    """Merge optional config with the policy; any attempt to loosen is clamped back to the policy."""
    return {
        "min_dte": max(MIN_DTE, min_dte), "max_dte": min(MAX_DTE, max_dte),
        "max_premium_usd": min(MAX_PREMIUM_USD, max_premium_usd),
        "contracts": CONTRACTS_PER_IDEA,
        "min_open_interest": min_open_interest, "max_spread_pct": max_spread_pct,
    }


def in_entry_window(local_time) -> bool:
    return ENTRY_START <= local_time < ENTRY_CUTOFF
