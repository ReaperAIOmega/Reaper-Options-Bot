from datetime import datetime, timedelta

from engine import CycleState, EngineConfig, run_cycle
from market_data import ET
from signals import generate_signal
from engine import load_sessions
from tests.fixtures import BULLISH_212, DAILY, FakeClient, build_rows

NOW = datetime(2026, 3, 11, 10, 0, tzinfo=ET)


def cfg(**kw):
    return EngineConfig(watchlist=["SPY"], **kw)


def test_end_to_end_bullish_212_produces_listed_call_once():
    client, state = FakeClient(), CycleState()
    first = run_cycle(client, cfg(), state, NOW)
    assert len(first["messages"]) == 1, first["skipped"]
    msg = first["messages"][0]
    assert "[SPY] Call idea" in msg and "110 call exp 2026-03-20" in msg and "No orders are placed" in msg
    assert "@everyone" not in msg
    second = run_cycle(client, cfg(), state, NOW + timedelta(minutes=15))
    assert second["messages"] == []
    assert second["skipped"]["SPY"] == ["duplicate_of_already_sent_signal"]


def test_signal_fields_are_deterministic():
    client = FakeClient()
    sig, reasons = generate_signal("SPY", client, load_sessions(client, NOW), NOW)
    assert reasons == ["signal"]
    assert sig["trend"] == "bullish" and sig["direction"] == "Call" and sig["setups"] == ["2-1-2"] and sig["score"] == 4
    assert sig["setup_bar_end"] == "2026-03-10T16:00:00-04:00"
    assert sig["dedupe_key"] == "SPY|bullish|2026-03-10T16:00:00-04:00|SPY260320C00110000"


def test_closed_market_does_nothing_and_fetches_nothing_else():
    client = FakeClient(clock_state="closed")
    out = run_cycle(client, cfg(), CycleState(), NOW)
    assert out == {"messages": [], "skipped": {}, "market": "closed"} and client.calls == ["clock"]


def test_stale_intraday_data_is_rejected():
    client = FakeClient(rows=build_rows(BULLISH_212, today_rows=False))
    sig, reasons = generate_signal("SPY", client, load_sessions(client, NOW), NOW)
    assert sig is None and reasons == ["stale_or_missing_intraday_data"]


def test_conflicting_continuity_suppresses_signal():
    bearish_daily = DAILY[:-2] + [{**DAILY[-2], "open": 110, "close": 101}] + DAILY[-1:]
    client = FakeClient(daily=bearish_daily)
    sig, reasons = generate_signal("SPY", client, load_sessions(client, NOW), NOW)
    assert sig is None and reasons == ["no_full_timeframe_continuity"]


def test_no_liquid_listed_contract_means_no_signal():
    client = FakeClient(chain_fn=lambda e: [])
    out = run_cycle(client, cfg(), CycleState(), NOW)
    assert out["messages"] == [] and out["skipped"]["SPY"] == ["no_listed_contract_meets_liquidity_rules"]


def test_daily_cap_is_enforced():
    state = CycleState(day=NOW.date(), sent_today=6)
    out = run_cycle(FakeClient(), cfg(max_per_day=6), state, NOW)
    assert out["messages"] == [] and out["skipped"]["SPY"] == ["signal_limit_reached"]


def test_bearish_bias_note_once_per_day_without_mentions():
    quotes = {"SPY": {"symbol": "SPY", "last": 109.5, "open": 111.0}, "QQQ": {"symbol": "QQQ", "last": 1, "open": 2}}
    state = CycleState()
    first = run_cycle(FakeClient(quotes=quotes), cfg(), state, NOW)
    second = run_cycle(FakeClient(quotes=quotes), cfg(), state, NOW + timedelta(minutes=15))
    notes = [m for m in first["messages"] + second["messages"] if m.startswith("Market check")]
    assert len(notes) == 1 and "@everyone" not in notes[0]


def test_discord_layer_imports_and_never_pings_by_default(monkeypatch):
    import importlib, sys
    for k, v in {"DISCORD_BOT_TOKEN": "x", "TRADIER_API_KEY": "x", "SIGNALS_CHANNEL_ID": "1", "WATCHLIST": "spy"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("MENTION_EVERYONE", raising=False)
    for m in ("config", "bot"):
        sys.modules.pop(m, None)
    bot = importlib.import_module("bot")
    assert bot.ALLOWED_MENTIONS.everyone is False and bot.ALLOWED_MENTIONS.roles is False
    assert bot.check_channel_permissions(None) == ["signals channel not found or not visible to the bot"]
