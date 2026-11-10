import os
from datetime import timedelta

from dotenv import load_dotenv

import policy

load_dotenv()


def _require(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name} (see .env.example)")
    return value


def _int(name, default):
    return int(os.getenv(name) or default)


DISCORD_BOT_TOKEN = _require("DISCORD_BOT_TOKEN")
TRADIER_API_KEY = _require("TRADIER_API_KEY")
# api.tradier.com needs a market-data entitlement; sandbox.tradier.com returns delayed data.
TRADIER_BASE_URL = os.getenv("TRADIER_BASE_URL", "https://api.tradier.com")
DATA_DELAY = timedelta(minutes=_int("DATA_DELAY_MINUTES", 0))

SIGNALS_CHANNEL_ID = int(_require("SIGNALS_CHANNEL_ID"))
# Policy symbols only (SPY, QQQ, IWM); other requested symbols are reported and ignored.
WATCHLIST, REJECTED_SYMBOLS = policy.effective_watchlist(os.getenv("WATCHLIST", "").split(","))

MAX_SIGNALS_PER_CYCLE = _int("MAX_SIGNALS_PER_CYCLE", 3)
MAX_SIGNALS_PER_DAY = _int("MAX_SIGNALS_PER_DAY", 6)
CYCLE_SECONDS = max(300, _int("CYCLE_SECONDS", 900))
# Off by default: the bot never pings @everyone/@here/roles unless explicitly enabled.
MENTION_EVERYONE = os.getenv("MENTION_EVERYONE", "false").lower() == "true"

# Environment can only tighten the owner policy (1-7 DTE, $200 max premium, 1 contract).
CONTRACT_RULES = policy.contract_rules(
    min_open_interest=_int("MIN_OPEN_INTEREST", 100),
    max_spread_pct=float(os.getenv("MAX_SPREAD_PCT") or 0.15),
    max_premium_usd=float(os.getenv("MAX_PREMIUM_USD") or policy.MAX_PREMIUM_USD),
    min_dte=_int("MIN_DTE", policy.MIN_DTE),
    max_dte=_int("MAX_DTE", policy.MAX_DTE),
)
