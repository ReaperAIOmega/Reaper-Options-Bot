import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TRADIER_API_KEY = os.getenv("TRADIER_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

SIGNALS_CHANNEL_ID = int(os.getenv("SIGNALS_CHANNEL_ID"))
NEWS_CHANNEL_ID = int(os.getenv("NEWS_CHANNEL_ID"))

WATCHLIST = os.getenv("WATCHLIST", "").split(",")

HEADERS = {
    "Authorization": f"Bearer {TRADIER_API_KEY}",
    "Accept": "application/json"
}

# Killzone times in EST (24h)
KILLZONES = {
    "pre_market": (9, 0),
    "market_open": (9, 30),
    "ten_am": (10, 0),
    "ny_killzone_open": (13, 30),   # 9:30am EST in UTC+4 is 13:30 UTC (adjust as needed)
    "ny_killzone_close": (20, 0),   # 4:00pm EST in UTC+4 is 20:00 UTC (adjust as needed)
    "three_thirty_pm": (15, 30)
}

MAX_SIGNALS = {
    "first_alert": 6,
    "subsequent_alerts": 3,
}

# Timeframes for analysis (Tradier supports these intervals)
TIMEFRAMES = ["120", "240", "D", "W", "M", "Q"]  # 2h, 4h, daily, weekly, monthly, quarterly

# Thresholds for scoring and filtering signals
MIN_SCORE = 2
