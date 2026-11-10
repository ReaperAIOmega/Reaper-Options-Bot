# Reaper Options Bot

Posts **informational, read-only** option setup ideas to one Discord channel. It never places,
stages or simulates orders. The Tradier client can only call `GET /v1/markets/*`.

## Owner policy (hard limits in `policy.py`; configuration can tighten, never loosen)
| Rule | Value |
|---|---|
| Symbols | SPY, QQQ, IWM only |
| Instrument and size | Options, **1 contract** per idea |
| Expiry | **1–7 DTE** (no 0DTE) |
| Premium | **≤ $200** at the ask (ask × 100 × 1) |
| Entry window | **09:45–15:00 ET** (no market data is requested outside it) |
| Qualification | **ICT, The Strat and the 15-minute ORB must each qualify independently and agree** |
| Quota | None. No qualifying setup means no message. A per-day cap only limits volume. |

## How a signal is produced
1. `/markets/clock` must report `open`; holidays and half days come from `/markets/calendar`.
2. 15-minute `/markets/timesales` rows (regular session) are aggregated into 120/240-minute bars anchored at
   the session open. Only completed bars with every 15-minute sub-bar present are used. Daily/weekly bars for
   the still-open period are dropped. Intraday data must be fresh (plus `DATA_DELAY_MINUTES`).
3. **The Strat:** full timeframe continuity (120, 240, daily, weekly) plus a 2-1-2 or failed-2U on 240 in the
   same direction.
4. **ICT:** the most recent 15-minute fair value gap is retested by the latest completed bar, which closes
   beyond it; a gap closed through in between is invalid.
5. **15-minute ORB:** the latest completed bar closes outside the 09:30–09:45 range.
6. The contract must be **listed** in `/markets/options/chains`, 1–7 DTE, bid/ask > 0, spread within
   `MAX_SPREAD_PCT`, open interest ≥ `MIN_OPEN_INTEREST`, and ask × 100 ≤ $200. The nearest five OTM strikes
   are scanned; otherwise no signal.
7. At most one idea per symbol and direction per day.

## Run
```
cp .env.example .env   # fill in tokens; never commit .env
pip install -r requirements.txt
python bot.py
```
Discord: give the bot role only **View Channel** and **Send Messages** on the signals channel.
`MENTION_EVERYONE` is off by default.

## Test
```
pip install -r requirements-dev.txt
python -m pytest -q
```
`tests/fixtures.py` is deterministic **synthetic** data. To add real recorded data:
`TRADIER_API_KEY=... python scripts/record_fixture.py SPY 2026-03-11T10:00`, review the JSON and commit it
under `tests/recorded/`; `tests/test_recorded.py` then replays it.

## Not yet verified
Live Tradier responses, entitlements and rate limits against a real account; recorded historical replay;
a Discord server run. Strategy edge is unproven: these are pattern detections, not tested trading results.
