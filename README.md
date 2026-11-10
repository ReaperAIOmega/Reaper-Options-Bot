# Reaper Options Bot

Posts **informational, read-only** option setup ideas to one Discord channel. It never places,
stages or simulates orders. The Tradier client can only call `GET /v1/markets/*`.

## How a signal is produced
1. `/markets/clock` must report `open`; holidays and half days come from `/markets/calendar`.
2. 15-minute `/markets/timesales` rows (regular session) are aggregated into 120/240-minute bars
   anchored at the session open. Only bars whose end has passed, and whose 15-minute sub-bars
   are all present, are used. Daily/weekly bars for the still-open period are dropped.
3. Intraday data must be fresh (latest completed 15-minute bar within ~20 minutes, plus
   `DATA_DELAY_MINUTES` for delayed feeds).
4. Full timeframe continuity (120, 240, daily, weekly) sets the direction. Any setup that
   disagrees with it suppresses the signal.
5. The contract must be **listed** in `/markets/options/chains` within `MIN_DTE..MAX_DTE`,
   with bid/ask > 0, spread within `MAX_SPREAD_PCT` and open interest ≥ `MIN_OPEN_INTEREST`.
   Otherwise no signal is sent.
6. Signals are de-duplicated by symbol, direction, setup bar and contract, and capped per cycle and per day.

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
