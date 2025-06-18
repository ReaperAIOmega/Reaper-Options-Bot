import requests
from config import HEADERS

BASE_URL = "https://api.tradier.com/v1/markets"

def get_quote(symbol):
    url = f"{BASE_URL}/quotes?symbols={symbol}"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    data = r.json()
    return data["quotes"]["quote"]

def get_candles(symbol, interval, start=None, end=None):
    # interval = 1, 5, 15, 30, 60, 120, 240, daily, weekly, monthly, quarterly
    url = f"{BASE_URL}/candles"
    params = {
        "symbol": symbol,
        "interval": interval,
        "start": start,
        "end": end,
    }
    r = requests.get(url, headers=HEADERS, params={k: v for k, v in params.items() if v})
    r.raise_for_status()
    data = r.json()
    # Return candles list: o,h,l,c,timestamp
    if "candles" in data and "candles" in data["candles"]:
        return data["candles"]["candles"]
    return []
