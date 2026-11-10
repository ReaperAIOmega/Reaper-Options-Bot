"""Session-aware candle construction from Tradier history and time-sales.

Rules (all times America/New_York, DST-aware via zoneinfo):
- Tradier has no 2h/4h interval. 120/240-minute bars are built from 15-minute
  time-sales, anchored to that day's session open from /markets/calendar
  (09:30 normally). The last bar of a session ends at the session close, so on a
  half day (13:00 close) it is shorter.
- A bar is "completed" only when its end time is at or before `now` (minus any
  data delay) AND every 15-minute sub-bar inside it is present. Bars with gaps are
  dropped rather than guessed.
- Daily/weekly/monthly bars for the current, still-open period are dropped.
- Closed calendar days (holidays/weekends) produce no session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BASE_MINUTES = 15


@dataclass(frozen=True)
class Session:
    day: date
    open: datetime
    close: datetime


def parse_et(value: str) -> datetime:
    """Tradier time-sales `time` is exchange-local ET without an offset."""
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(ET) if parsed.tzinfo else parsed.replace(tzinfo=ET)


def sessions_from_calendar(days: list[dict]) -> dict[date, Session]:
    sessions = {}
    for d in days:
        if d.get("status") != "open" or not isinstance(d.get("open"), dict):
            continue
        day = date.fromisoformat(d["date"])
        start = time.fromisoformat(d["open"]["start"])
        end = time.fromisoformat(d["open"]["end"])
        sessions[day] = Session(day, datetime.combine(day, start, ET), datetime.combine(day, end, ET))
    return sessions


def aggregate_intraday(rows: list[dict], minutes: int, sessions: dict[date, Session], now: datetime,
                       delay: timedelta = timedelta(0)) -> list[dict]:
    if minutes % BASE_MINUTES:
        raise ValueError("Bar size must be a multiple of 15 minutes")
    cutoff = now.astimezone(ET) - delay
    buckets: dict[tuple[date, int], list[tuple[datetime, dict]]] = {}
    for row in rows:
        start = parse_et(row["time"])
        session = sessions.get(start.date())
        if session is None or not (session.open <= start < session.close):
            continue  # outside the regular session or on a non-trading day
        index = int((start - session.open).total_seconds() // (minutes * 60))
        buckets.setdefault((start.date(), index), []).append((start, row))

    bars = []
    for (day, index), items in sorted(buckets.items()):
        session = sessions[day]
        bar_start = session.open + timedelta(minutes=minutes * index)
        bar_end = min(bar_start + timedelta(minutes=minutes), session.close)
        if bar_end > cutoff:
            continue  # still forming
        items.sort(key=lambda item: item[0])
        expected = int((bar_end - bar_start).total_seconds() // (BASE_MINUTES * 60))
        starts = [s for s, _ in items]
        if len(set(starts)) != expected or starts[0] != bar_start:
            continue  # data gap: never fabricate a bar
        rows_ = [r for _, r in items]
        bars.append({
            "start": bar_start, "end": bar_end,
            "open": rows_[0]["open"], "close": rows_[-1]["close"],
            "high": max(r["high"] for r in rows_), "low": min(r["low"] for r in rows_),
            "volume": sum(r.get("volume", 0) for r in rows_),
        })
    return bars


def completed_history(rows: list[dict], interval: str, now: datetime, sessions: dict[date, Session]) -> list[dict]:
    """Drop the bar for the still-open day, week or month."""
    local = now.astimezone(ET)
    today = local.date()
    today_session = sessions.get(today)
    day_closed = today_session is None or local >= today_session.close
    out = []
    for row in rows:
        d = date.fromisoformat(row["date"])
        if interval == "daily":
            if d > today or (d == today and not day_closed):
                continue
        elif interval == "weekly":
            # The current week's bar is final only once its last session has closed.
            if d >= today - timedelta(days=today.weekday()) and not (day_closed and not _later_session_this_week(today, sessions)):
                continue
        elif interval == "monthly":
            if (d.year, d.month) == (today.year, today.month) and not (day_closed and not _later_session_this_month(today, sessions)):
                continue
        else:
            raise ValueError(f"Unsupported history interval {interval}")
        out.append({**row, "start": d})
    return out


def _later_session_this_week(today: date, sessions: dict[date, Session]) -> bool:
    return any(d > today and d.isocalendar()[:2] == today.isocalendar()[:2] for d in sessions)


def _later_session_this_month(today: date, sessions: dict[date, Session]) -> bool:
    return any(d > today and (d.year, d.month) == (today.year, today.month) for d in sessions)


def is_fresh(bars: list[dict], minutes: int, now: datetime, delay: timedelta = timedelta(0),
             tolerance: timedelta = timedelta(minutes=5)) -> bool:
    """The newest completed intraday bar must have closed within one bar period of `now`."""
    if not bars:
        return False
    age = now.astimezone(ET) - delay - bars[-1]["end"]
    return timedelta(0) <= age <= timedelta(minutes=minutes) + tolerance
