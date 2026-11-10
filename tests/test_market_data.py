from datetime import date, datetime, timedelta

from market_data import ET, aggregate_intraday, completed_history, is_fresh, sessions_from_calendar
from tests.fixtures import calendar_month, sub_bars


def sessions(*months):
    days = []
    for y, m in months:
        days += calendar_month(y, m)
    return sessions_from_calendar(days)


def at(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=ET)


def full_day(day, close="16:00"):
    return sub_bars(day, "09:30", close, 100, 101, 99, 100.5)


def test_240_bars_anchor_to_session_open_and_last_bar_ends_at_close():
    s = sessions((2026, 3))
    bars = aggregate_intraday(full_day(date(2026, 3, 10)), 240, s, at(2026, 3, 10, 16, 0))
    assert [(b["start"].strftime("%H:%M"), b["end"].strftime("%H:%M")) for b in bars] == [("09:30", "13:30"), ("13:30", "16:00")]


def test_120_bars_and_dst_offsets():
    s = sessions((2026, 3))
    bars = aggregate_intraday(full_day(date(2026, 3, 10)), 120, s, at(2026, 3, 10, 16, 0))
    assert [b["start"].strftime("%H:%M") for b in bars] == ["09:30", "11:30", "13:30", "15:30"]
    assert bars[0]["start"].utcoffset() == timedelta(hours=-4)  # EDT after 2026-03-08
    winter = aggregate_intraday(full_day(date(2026, 3, 6)), 120, s, at(2026, 3, 6, 16, 0))
    assert winter[0]["start"].utcoffset() == timedelta(hours=-5)


def test_forming_bar_excluded_until_its_end():
    s = sessions((2026, 3))
    rows = full_day(date(2026, 3, 10))
    assert aggregate_intraday(rows, 240, s, at(2026, 3, 10, 13, 29)) == []
    assert len(aggregate_intraday(rows, 240, s, at(2026, 3, 10, 13, 30))) == 1
    assert aggregate_intraday(rows, 240, s, at(2026, 3, 10, 13, 40), delay=timedelta(minutes=15)) == []


def test_gap_in_sub_bars_drops_the_bar_instead_of_guessing():
    s = sessions((2026, 3))
    rows = [r for r in full_day(date(2026, 3, 10)) if not r["time"].endswith("10:45:00")]
    bars = aggregate_intraday(rows, 240, s, at(2026, 3, 10, 16, 0))
    assert [b["start"].strftime("%H:%M") for b in bars] == ["13:30"]


def test_half_day_and_holiday():
    s = sessions((2026, 11))
    half = aggregate_intraday(full_day(date(2026, 11, 27), "13:00"), 240, s, at(2026, 11, 27, 13, 0))
    assert [(b["start"].strftime("%H:%M"), b["end"].strftime("%H:%M")) for b in half] == [("09:30", "13:00")]
    assert date(2026, 11, 26) not in s
    assert aggregate_intraday(full_day(date(2026, 11, 26)), 240, s, at(2026, 11, 26, 16, 0)) == []


def test_completed_history_drops_open_periods():
    s = sessions((2026, 3))
    rows = [{"date": "2026-03-09"}, {"date": "2026-03-10"}]
    assert [r["date"] for r in completed_history(rows, "daily", at(2026, 3, 10, 12, 0), s)] == ["2026-03-09"]
    assert [r["date"] for r in completed_history(rows, "daily", at(2026, 3, 10, 16, 0), s)] == ["2026-03-09", "2026-03-10"]
    weeks = [{"date": "2026-03-02"}, {"date": "2026-03-09"}]
    assert [r["date"] for r in completed_history(weeks, "weekly", at(2026, 3, 11, 12, 0), s)] == ["2026-03-02"]
    assert [r["date"] for r in completed_history(weeks, "weekly", at(2026, 3, 13, 16, 1), s)] == ["2026-03-02", "2026-03-09"]


def test_freshness():
    s = sessions((2026, 3))
    bars = aggregate_intraday(full_day(date(2026, 3, 10)), 15, s, at(2026, 3, 10, 11, 0))
    assert is_fresh(bars, 15, at(2026, 3, 10, 11, 0))
    assert not is_fresh(bars, 15, at(2026, 3, 10, 11, 30))
    assert not is_fresh([], 15, at(2026, 3, 10, 11, 0))
