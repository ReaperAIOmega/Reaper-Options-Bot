"""Choose a real, listed option contract or nothing. Never synthesize a strike or expiry."""

from __future__ import annotations

from datetime import date
from typing import Callable

from strategy import BULL


def select_contract(direction: str, underlying_price: float, today: date, expirations: list[str],
                    load_chain: Callable[[str], list[dict]], *, min_dte: int = 5, max_dte: int = 21,
                    min_open_interest: int = 100, max_spread_pct: float = 0.15) -> dict | None:
    if underlying_price is None or underlying_price <= 0:
        return None
    option_type = "call" if direction == BULL else "put"
    candidates = sorted(
        e for e in expirations
        if min_dte <= (date.fromisoformat(e) - today).days <= max_dte
    )
    for expiration in candidates:
        listed = [o for o in load_chain(expiration)
                  if o.get("option_type") == option_type and o.get("expiration_date") == expiration]
        if option_type == "call":
            otm = sorted((o for o in listed if o["strike"] > underlying_price), key=lambda o: o["strike"])
        else:
            otm = sorted((o for o in listed if o["strike"] < underlying_price), key=lambda o: -o["strike"])
        for option in otm[:3]:  # nearest out-of-the-money strikes only
            bid, ask = option.get("bid") or 0, option.get("ask") or 0
            if bid <= 0 or ask <= 0 or ask < bid:
                continue
            mid = (bid + ask) / 2
            if (ask - bid) / mid > max_spread_pct:
                continue
            if (option.get("open_interest") or 0) < min_open_interest:
                continue
            return {
                "option_symbol": option["symbol"], "option_type": option_type,
                "strike": option["strike"], "expiration": expiration,
                "dte": (date.fromisoformat(expiration) - today).days,
                "bid": bid, "ask": ask, "mid": round(mid, 2),
                "open_interest": option.get("open_interest"),
            }
    return None
