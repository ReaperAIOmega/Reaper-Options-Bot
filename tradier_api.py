"""Read-only Tradier market-data client.

Only documented GET endpoints under /v1/markets/ are reachable. There is no
order, account or streaming-session code in this module, and `_get` refuses any
other path, so the bot cannot place trades through this client.

Endpoints used (Tradier Brokerage API, market data):
  /v1/markets/clock                       market state (open/closed/premarket/postmarket)
  /v1/markets/calendar                    session hours per day, holidays, half days
  /v1/markets/quotes                      last/open/bid/ask
  /v1/markets/history                     daily / weekly / monthly bars
  /v1/markets/timesales                   intraday 1min / 5min / 15min bars
  /v1/markets/options/expirations         listed expirations
  /v1/markets/options/chains              listed contracts for one expiration
"""

from __future__ import annotations

import time as _time
from typing import Any, Callable

import requests

ALLOWED_PREFIX = "/v1/markets/"
INTRADAY_INTERVALS = {"1min", "5min", "15min"}
HISTORY_INTERVALS = {"daily", "weekly", "monthly"}


class TradierError(RuntimeError):
    pass


def as_list(value: Any) -> list:
    """Tradier returns a bare object instead of a one-element list, and null for none."""
    if value is None or value == "null":
        return []
    return value if isinstance(value, list) else [value]


class TradierClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://api.tradier.com",
        session: requests.Session | None = None,
        max_retries: int = 3,
        sleep: Callable[[float], None] = _time.sleep,
        timeout: float = 10.0,
    ):
        if not token:
            raise ValueError("Tradier token required")
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
        self.max_retries = max_retries
        self.sleep = sleep
        self.timeout = timeout
        self.rate_limit_available: int | None = None

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not path.startswith(ALLOWED_PREFIX) or ".." in path:
            raise TradierError(f"Refusing non-market-data path: {path}")
        params = {k: v for k, v in (params or {}).items() if v is not None}
        for attempt in range(self.max_retries + 1):
            response = self.session.get(self.base_url + path, params=params, timeout=self.timeout)
            available = response.headers.get("X-Ratelimit-Available")
            if available is not None and available.isdigit():
                self.rate_limit_available = int(available)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == self.max_retries:
                    break
                expiry = response.headers.get("X-Ratelimit-Expiry")
                wait = 2 ** attempt
                if response.status_code == 429 and expiry and expiry.isdigit():
                    wait = max(1.0, min(60.0, int(expiry) / 1000 - _time.time()))
                self.sleep(wait)
                continue
            if response.status_code in (401, 403):
                raise TradierError(f"Tradier rejected credentials or entitlement ({response.status_code}) for {path}")
            if response.status_code != 200:
                raise TradierError(f"Tradier {path} returned HTTP {response.status_code}")
            try:
                return response.json()
            except ValueError as exc:
                raise TradierError(f"Tradier {path} returned non-JSON body") from exc
        raise TradierError(f"Tradier {path} still failing after {self.max_retries} retries (HTTP {response.status_code})")

    def clock(self) -> dict:
        return self._get("/v1/markets/clock").get("clock") or {}

    def calendar(self, year: int, month: int) -> list[dict]:
        data = self._get("/v1/markets/calendar", {"year": year, "month": f"{month:02d}"})
        return as_list(((data.get("calendar") or {}).get("days") or {}).get("day"))

    def quotes(self, symbols: list[str]) -> dict[str, dict]:
        data = self._get("/v1/markets/quotes", {"symbols": ",".join(symbols), "greeks": "false"})
        return {q["symbol"]: q for q in as_list((data.get("quotes") or {}).get("quote"))}

    def history(self, symbol: str, interval: str, start: str, end: str) -> list[dict]:
        if interval not in HISTORY_INTERVALS:
            raise ValueError(f"Unsupported history interval {interval}")
        data = self._get("/v1/markets/history", {"symbol": symbol, "interval": interval, "start": start, "end": end})
        return as_list((data.get("history") or {}).get("day"))

    def timesales(self, symbol: str, interval: str, start: str, end: str) -> list[dict]:
        if interval not in INTRADAY_INTERVALS:
            raise ValueError(f"Unsupported timesales interval {interval}")
        data = self._get(
            "/v1/markets/timesales",
            {"symbol": symbol, "interval": interval, "start": start, "end": end, "session_filter": "open"},
        )
        return as_list((data.get("series") or {}).get("data"))

    def option_expirations(self, symbol: str) -> list[str]:
        data = self._get("/v1/markets/options/expirations", {"symbol": symbol, "includeAllRoots": "false", "strikes": "false"})
        return as_list((data.get("expirations") or {}).get("date"))

    def option_chain(self, symbol: str, expiration: str) -> list[dict]:
        data = self._get("/v1/markets/options/chains", {"symbol": symbol, "expiration": expiration, "greeks": "false"})
        return as_list((data.get("options") or {}).get("option"))
