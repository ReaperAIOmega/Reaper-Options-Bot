"""Record a real Tradier market-data snapshot for deterministic replay tests (read-only GETs).

Usage: TRADIER_API_KEY=... python scripts/record_fixture.py SPY 2026-03-11T10:00
Writes tests/recorded/<SYMBOL>_<timestamp>.json. Review the file before committing it:
it contains only public market data, never account data.
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from market_data import ET  # noqa: E402
from tradier_api import TradierClient  # noqa: E402


def main(symbol: str, at: str):
    now = datetime.fromisoformat(at).replace(tzinfo=ET)
    c = TradierClient(os.environ["TRADIER_API_KEY"], os.getenv("TRADIER_BASE_URL", "https://api.tradier.com"))
    months = {((now - timedelta(days=d)).year, (now - timedelta(days=d)).month) for d in (0, 40)}
    expirations = c.option_expirations(symbol)
    snap = {
        "symbol": symbol, "now": now.isoformat(), "source": c.base_url,
        "calendar": [d for y, m in sorted(months) for d in c.calendar(y, m)],
        "timesales": c.timesales(symbol, "15min", (now - timedelta(days=30)).strftime("%Y-%m-%d 09:30"), now.strftime("%Y-%m-%d %H:%M")),
        "daily": c.history(symbol, "daily", (now - timedelta(days=180)).date().isoformat(), now.date().isoformat()),
        "weekly": c.history(symbol, "weekly", (now - timedelta(days=730)).date().isoformat(), now.date().isoformat()),
        "quotes": c.quotes([symbol, "SPY", "QQQ"]),
        "expirations": expirations,
        "chains": {e: c.option_chain(symbol, e) for e in expirations[:4]},
    }
    out = Path(__file__).resolve().parents[1] / "tests" / "recorded" / f"{symbol}_{now:%Y%m%dT%H%M}.json"
    out.write_text(json.dumps(snap, indent=1, sort_keys=True))
    print(out)


if __name__ == "__main__":
    main(sys.argv[1].upper(), sys.argv[2])
