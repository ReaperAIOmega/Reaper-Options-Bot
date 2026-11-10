from datetime import datetime, timedelta

from engine import CycleState, EngineConfig, load_sessions, run_cycle
from market_data import ET
from signals import generate_signal
from tests.fixtures import BULLISH_212, DAILY, FakeClient, bar, build_rows, today_bars

NOW = datetime(2026, 3, 11, 10, 30, tzinfo=ET)


def cfg(**kw):
    return EngineConfig(watchlist=["SPY"], **kw)


def sig(client, now=NOW):
    return generate_signal("SPY", client, load_sessions(client, now), now)


def test_all_three_qualifications_produce_one_policy_contract_once():
    client, state = FakeClient(), CycleState()
    first = run_cycle(client, cfg(), state, NOW)
    assert len(first["messages"]) == 1, first["skipped"]
    msg = first["messages"][0]
    assert "[SPY] Call idea" in msg and "ICT + Strat (2-1-2) + 15m ORB" in msg
    assert "115 call exp 2026-03-13 (2 DTE)" in msg and "Size: 1 contract" in msg and "max premium $110.00" in msg
    assert "No orders are placed" in msg and "@everyone" not in msg
    second = run_cycle(client, cfg(), state, NOW + timedelta(minutes=15))
    assert second["messages"] == [] and second["skipped"]["SPY"] == ["duplicate_of_already_sent_signal"]


def test_signal_fields_are_deterministic():
    s, reasons = sig(FakeClient())
    assert reasons == ["signal"]
    assert s["trend"] == "bullish" and s["qualifications"] == ["ict", "orb15", "strat"] and s["strat_setups"] == ["2-1-2"]
    assert s["opening_range"] == {"high": 110.0, "low": 109.4}
    assert s["contract"]["max_premium_usd"] == 110.0 and s["contract"]["contracts"] == 1
    assert s["dedupe_key"] == "SPY|bullish|2026-03-11"


def test_entry_window_is_enforced_before_any_market_data_call():
    for t in [(9, 44), (15, 0), (15, 30), (9, 30)]:
        client = FakeClient()
        out = run_cycle(client, cfg(), CycleState(), NOW.replace(hour=t[0], minute=t[1]))
        assert out == {"messages": [], "skipped": {}, "market": "outside_entry_window"} and client.calls == []
    assert sig(FakeClient(), NOW.replace(hour=14, minute=59))[1] != ["outside_entry_window"]
    assert sig(FakeClient(), NOW.replace(hour=9, minute=45))[1] != ["outside_entry_window"]


def test_symbols_outside_policy_are_refused():
    out = run_cycle(FakeClient(), EngineConfig(watchlist=["SPY", "TSLA"]), CycleState(), NOW)
    assert out["skipped"]["TSLA"] == ["symbol_not_in_policy"] and len(out["messages"]) == 1
    assert generate_signal("AAPL", FakeClient(), {}, NOW) == (None, ["symbol_not_in_policy"])


def test_missing_ict_or_orb_blocks_the_signal():
    no_gap = today_bars()[:2] + [bar(NOW.date(), "10:00", 110.5, 111.2, 110.4, 111.1), bar(NOW.date(), "10:15", 111.1, 111.3, 110.9, 111.2)]
    s, reasons = sig(FakeClient(rows=build_rows(BULLISH_212, today_rows=no_gap)))
    assert s is None and reasons == ["missing_qualification:ict"]
    inside_range = today_bars()[:3] + [bar(NOW.date(), "10:15", 111.4, 111.5, 109.5, 109.9)]
    s, reasons = sig(FakeClient(rows=build_rows(BULLISH_212, today_rows=inside_range)))
    assert s is None and "orb15" in reasons[0]


def test_strat_bullish_but_ict_and_orb_bearish_is_refused():
    d = NOW.date()
    bearish_today = [bar(d, "09:30", 109.5, 110.0, 109.4, 109.8), bar(d, "09:45", 109.8, 109.8, 109.1, 109.2),
                     bar(d, "10:00", 108.6, 108.6, 108.0, 108.1), bar(d, "10:15", 108.1, 108.8, 108.0, 108.3)]
    s, reasons = sig(FakeClient(rows=build_rows(BULLISH_212, today_rows=bearish_today)))
    assert s is None and reasons == ["qualifications_disagree:ict=bearish,orb15=bearish,strat=bullish"]


def test_missing_strat_continuity_blocks_the_signal():
    bearish_daily = DAILY[:-2] + [{**DAILY[-2], "open": 110, "close": 101}] + DAILY[-1:]
    s, reasons = sig(FakeClient(daily=bearish_daily))
    assert s is None and reasons[0] == "missing_qualification:strat" and "no_full_timeframe_continuity" in reasons


def test_stale_intraday_data_is_rejected():
    s, reasons = sig(FakeClient(rows=build_rows(BULLISH_212, today_rows=False)))
    assert s is None and reasons == ["stale_or_missing_intraday_data"]


def test_no_contract_within_premium_cap_or_dte_means_no_signal():
    from tests.fixtures import chain
    pricey = lambda e: [{**o, "bid": 3.0, "ask": 3.1} for o in chain(e)]
    assert sig(FakeClient(chain_fn=pricey)) == (None, ["no_listed_contract_within_policy"])
    assert sig(FakeClient(expirations=["2026-03-11", "2026-03-20"])) == (None, ["no_listed_contract_within_policy"])


def test_no_quota_nothing_qualifies_means_nothing_sent():
    client = FakeClient(rows=build_rows(BULLISH_212, today_rows=today_bars()[:2]))
    out = run_cycle(client, cfg(), CycleState(), NOW.replace(hour=10, minute=0))
    assert out["messages"] == [] and out["skipped"]["SPY"]


def test_daily_cap_is_enforced():
    state = CycleState(day=NOW.date(), sent_today=6)
    out = run_cycle(FakeClient(), cfg(max_per_day=6), state, NOW)
    assert out["messages"] == [] and out["skipped"]["SPY"] == ["signal_limit_reached"]


def test_bearish_bias_note_once_per_day_without_mentions():
    quotes = {"SPY": {"symbol": "SPY", "last": 111.0, "open": 112.0}, "QQQ": {"symbol": "QQQ", "last": 1, "open": 2}}
    state = CycleState()
    first = run_cycle(FakeClient(quotes=quotes), cfg(), state, NOW)
    second = run_cycle(FakeClient(quotes=quotes), cfg(), state, NOW + timedelta(minutes=15))
    notes = [m for m in first["messages"] + second["messages"] if m.startswith("Market check")]
    assert len(notes) == 1 and "@everyone" not in notes[0]


def test_discord_layer_imports_and_never_pings_by_default(monkeypatch):
    import importlib, sys
    for k, v in {"DISCORD_BOT_TOKEN": "x", "TRADIER_API_KEY": "x", "SIGNALS_CHANNEL_ID": "1", "WATCHLIST": "spy,tsla",
                 "MAX_DTE": "30", "MAX_PREMIUM_USD": "500"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("MENTION_EVERYONE", raising=False)
    for m in ("config", "bot"):
        sys.modules.pop(m, None)
    config = importlib.import_module("config")
    assert config.WATCHLIST == ["SPY"] and config.REJECTED_SYMBOLS == ["TSLA"]
    assert config.CONTRACT_RULES["max_dte"] == 7 and config.CONTRACT_RULES["max_premium_usd"] == 200.0, "env cannot loosen policy"
    bot = importlib.import_module("bot")
    assert bot.ALLOWED_MENTIONS.everyone is False and bot.ALLOWED_MENTIONS.roles is False
    assert bot.check_channel_permissions(None) == ["signals channel not found or not visible to the bot"]
