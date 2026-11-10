import os
from datetime import timedelta

from dotenv import load_dotenv

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
WATCHLIST = [s.strip().upper() for s in os.getenv("WATCHLIST", "").split(",") if s.strip()]

MIN_SCORE = _int("MIN_SCORE", 4)
MAX_SIGNALS_PER_CYCLE = _int("MAX_SIGNALS_PER_CYCLE", 3)
MAX_SIGNALS_PER_DAY = _int("MAX_SIGNALS_PER_DAY", 6)
CYCLE_SECONDS = max(300, _int("CYCLE_SECONDS", 900))
# Off by default: the bot never pings @everyone/@here/roles unless explicitly enabled.
MENTION_EVERYONE = os.getenv("MENTION_EVERYONE", "false").lower() == "true"

CONTRACT_RULES = {
    "min_dte": _int("MIN_DTE", 5),
    "max_dte": _int("MAX_DTE", 21),
    "min_open_interest": _int("MIN_OPEN_INTEREST", 100),
    "max_spread_pct": float(os.getenv("MAX_SPREAD_PCT") or 0.15),
}
