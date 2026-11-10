"""Replay recorded real market snapshots. Skips until a snapshot is recorded and committed."""
import json
from datetime import datetime
from pathlib import Path

import pytest

from engine import load_sessions
from market_data import aggregate_intraday
from signals import generate_signal

SNAPSHOTS = sorted((Path(__file__).parent / "recorded").glob("*.json"))


class Replay:
    def __init__(self, snap):
        self.s = snap

    def clock(self):
        return {"state": "open"}

    def calendar(self, year, month):
        return [d for d in self.s["calendar"] if d["date"].startswith(f"{year}-{month:02d}")]

    def quotes(self, symbols):
        return {k: v for k, v in self.s["quotes"].items() if k in symbols}

    def timesales(self, *a):
        return self.s["timesales"]

    def history(self, symbol, interval, *a):
        return self.s[interval]

    def option_expirations(self, symbol):
        return self.s["expirations"]

    def option_chain(self, symbol, expiration):
        return self.s["chains"].get(expiration, [])


@pytest.mark.skipif(not SNAPSHOTS, reason="no recorded Tradier snapshot yet (needs credentials)")
@pytest.mark.parametrize("path", SNAPSHOTS, ids=lambda p: p.name)
def test_recorded_snapshot_is_deterministic_and_never_invents_contracts(path):
    snap = json.loads(path.read_text())
    now = datetime.fromisoformat(snap["now"])
    client = Replay(snap)
    sessions = load_sessions(client, now)
    assert aggregate_intraday(snap["timesales"], 240, sessions, now)
    first = generate_signal(snap["symbol"], client, sessions, now)
    assert first == generate_signal(snap["symbol"], client, sessions, now)
    sig, _ = first
    if sig:
        listed = {o["symbol"] for chain in snap["chains"].values() for o in chain}
        assert sig["contract"]["option_symbol"] in listed
