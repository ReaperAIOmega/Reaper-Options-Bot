"""Deterministic SYNTHETIC market fixtures shaped like Tradier responses.

These are constructed price paths, not recorded market history. They exercise
session anchoring, completion, DST and pattern logic exactly and repeatably.
Recorded fixtures (scripts/record_fixture.py) are a separate, later gate.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from market_data import ET

HALF_DAYS = {date(2026, 11, 27): "13:00"}
HOLIDAYS = {date(2026, 11, 26), date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16)}


def calendar_month(year, month):
    days, d = [], date(year, month, 1)
    while d.month == month:
        if d.weekday() < 5 and d not in HOLIDAYS:
            days.append({"date": d.isoformat(), "status": "open", "open": {"start": "09:30", "end": HALF_DAYS.get(d, "16:00")}})
        else:
            days.append({"date": d.isoformat(), "status": "closed"})
        d += timedelta(days=1)
    return days


def sub_bars(day: date, start: str, end: str, o: float, h: float, l: float, c: float):
    """15-minute rows whose aggregate is exactly (o, h, l, c); each row moves in the bar's direction."""
    t = datetime.combine(day, time.fromisoformat(start), ET)
    stop = datetime.combine(day, time.fromisoformat(end), ET)
    n = int((stop - t).total_seconds() // 900)
    rows, price = [], o
    for i in range(n):
        nxt = o + (c - o) * (i + 1) / n
        lo, hi = min(price, nxt), max(price, nxt)
        if i == 0:
            hi = max(hi, h) if c >= o else hi
            lo = min(lo, l) if c < o else lo
        if i == n - 1:
            hi = max(hi, h)
            lo = min(lo, l)
        rows.append({"time": t.strftime("%Y-%m-%dT%H:%M:%S"), "timestamp": int(t.timestamp()),
                     "open": round(price, 4), "high": round(hi, 4), "low": round(lo, 4), "close": round(nxt, 4),
                     "volume": 1000, "price": round(nxt, 4), "vwap": round((price + nxt) / 2, 4)})
        price, t = nxt, t + timedelta(minutes=15)
    return rows


# Four-hour bars (AM 09:30-13:30, PM 13:30-16:00). The last three completed bars before
# 2026-03-11 10:00 ET form a bullish 2-1-2: bearish 03-09 PM, inside 03-10 AM, breakout 03-10 PM.
BULLISH_212 = [
    (date(2026, 3, 5), "AM", 100, 104, 99, 103), (date(2026, 3, 5), "PM", 103, 105, 102, 104),
    (date(2026, 3, 6), "AM", 104, 106, 103, 105), (date(2026, 3, 6), "PM", 105, 107, 104, 106),
    (date(2026, 3, 9), "AM", 106, 111, 105, 109), (date(2026, 3, 9), "PM", 109, 110, 100, 101),
    (date(2026, 3, 10), "AM", 101, 108, 102, 107), (date(2026, 3, 10), "PM", 107, 110, 106, 109.5),
]


def build_rows(bars, today_rows=True, today=date(2026, 3, 11)):
    rows = []
    for day, half, o, h, l, c in bars:
        if half == "AM":
            rows += sub_bars(day, "09:30", "13:30", o, h, l, c)
        else:
            rows += sub_bars(day, "13:30", "16:00", o, h, l, c)
    if today_rows:
        rows += today_bars(today) if today_rows is True else today_rows
    return rows


def bar(day, hhmm, o, h, l, c):
    t = datetime.combine(day, time.fromisoformat(hhmm), ET)
    return {"time": t.strftime("%Y-%m-%dT%H:%M:%S"), "timestamp": int(t.timestamp()), "open": o, "high": h, "low": l,
            "close": c, "volume": 1000, "price": c, "vwap": (o + c) / 2}


def today_bars(day=date(2026, 3, 11)):
    """09:30 bar = opening range 109.4-110. 10:00 bar gaps above it (bullish FVG 110-110.8).
    10:15 bar trades back into the gap (low 110.6) and closes above it (111.0), above the opening range."""
    return [bar(day, "09:30", 109.5, 110.0, 109.4, 109.8), bar(day, "09:45", 109.8, 110.6, 109.8, 110.5),
            bar(day, "10:00", 110.8, 111.5, 110.8, 111.4), bar(day, "10:15", 111.4, 111.5, 110.6, 111.0)]


DAILY = [{"date": d.isoformat(), "open": o, "high": h, "low": l, "close": c, "volume": 1}
         for d, o, h, l, c in [(date(2026, 3, 4), 98, 100, 97, 99), (date(2026, 3, 5), 100, 105, 99, 104),
                               (date(2026, 3, 6), 104, 107, 103, 106), (date(2026, 3, 9), 106, 111, 100, 101),
                               (date(2026, 3, 10), 101, 110, 101, 109.5), (date(2026, 3, 11), 109.5, 110, 109.4, 109.8)]]
WEEKLY = [{"date": d, "open": o, "high": h, "low": l, "close": c, "volume": 1}
          for d, o, h, l, c in [("2026-02-09", 90, 95, 89, 94), ("2026-02-16", 94, 96, 92, 95),
                                ("2026-02-23", 95, 99, 94, 98), ("2026-03-02", 98, 107, 97, 106),
                                ("2026-03-09", 106, 111, 100, 109.8)]]

EXPIRATIONS = ["2026-03-13", "2026-03-20", "2026-04-17"]


def chain(expiration, *, price=109.5, oi=500, spread=0.10):
    out = []
    for strike in (100, 105, 110, 115, 120):
        for kind in ("call", "put"):
            intrinsic = max(0, price - strike) if kind == "call" else max(0, strike - price)
            bid = round(intrinsic + 1.0, 2)
            out.append({"symbol": f"SPY{expiration.replace('-', '')[2:]}{kind[0].upper()}{strike:05d}000",
                        "strike": strike, "option_type": kind, "expiration_date": expiration,
                        "bid": bid, "ask": round(bid + spread, 2), "open_interest": oi})
    return out


class FakeClient:
    """Implements the TradierClient read methods over fixtures; records every call."""

    def __init__(self, rows=None, daily=DAILY, weekly=WEEKLY, clock_state="open", quotes=None,
                 expirations=EXPIRATIONS, chain_fn=chain):
        self.rows = build_rows(BULLISH_212) if rows is None else rows
        self.daily, self.weekly, self.clock_state = daily, weekly, clock_state
        self._quotes = quotes or {"SPY": {"symbol": "SPY", "last": 111.0, "open": 108.0},
                                  "QQQ": {"symbol": "QQQ", "last": 400.0, "open": 398.0}}
        self.expirations, self.chain_fn, self.calls = expirations, chain_fn, []

    def clock(self):
        self.calls.append("clock")
        return {"state": self.clock_state}

    def calendar(self, year, month):
        return calendar_month(year, month)

    def quotes(self, symbols):
        return {s: self._quotes[s] for s in symbols if s in self._quotes}

    def timesales(self, symbol, interval, start, end):
        assert interval == "15min"
        end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M").replace(tzinfo=ET)
        return [r for r in self.rows if datetime.fromisoformat(r["time"]).replace(tzinfo=ET) < end_dt]

    def history(self, symbol, interval, start, end):
        return self.daily if interval == "daily" else self.weekly

    def option_expirations(self, symbol):
        return self.expirations

    def option_chain(self, symbol, expiration):
        return self.chain_fn(expiration)
