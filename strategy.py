"""Price-pattern detectors. Every detector returns a direction or None; none of them guesses.

Candles are dicts with open/high/low/close, oldest first.
"""

from __future__ import annotations

BULL, BEAR = "bullish", "bearish"


def _up(c):
    return c["close"] > c["open"]


def _down(c):
    return c["close"] < c["open"]


def is_inside_bar(prev, cur):
    return cur["high"] < prev["high"] and cur["low"] > prev["low"]


def two_one_two(candles):
    """2-1-2 reversal: directional bar, inside bar, breakout of the inside bar the other way."""
    if len(candles) < 3:
        return None
    c1, c2, c3 = candles[-3:]
    if not is_inside_bar(c1, c2):
        return None
    if _down(c1) and c3["close"] > c2["high"]:
        return BULL
    if _up(c1) and c3["close"] < c2["low"]:
        return BEAR
    return None


def failed_2u(candles):
    """Two up bars, then a bar that opens above and closes below the prior close: bearish."""
    if len(candles) < 3:
        return None
    c1, c2, c3 = candles[-3:]
    if _up(c1) and _up(c2) and c3["open"] > c2["close"] and c3["close"] < c2["close"]:
        return BEAR
    return None


def fvg_retest(candles):
    """Three-candle fair value gap (c1..c3) retested and respected by the latest bar.

    Bullish gap: c1.high < c3.low; the latest bar trades into the gap but closes above c1.high.
    Bearish gap: c1.low > c3.high; the latest bar trades into the gap but closes below c1.low.
    """
    if len(candles) < 4:
        return None
    c1, _, c3, last = candles[-4:]
    if c1["high"] < c3["low"] and last["low"] <= c3["low"] and last["close"] > c1["high"]:
        return BULL
    if c1["low"] > c3["high"] and last["high"] >= c3["high"] and last["close"] < c1["low"]:
        return BEAR
    return None


def ftfc_direction(candles_by_tf: dict[str, list]) -> str | None:
    """Full timeframe continuity: the latest completed bar on every timeframe points the same way."""
    directions = set()
    for candles in candles_by_tf.values():
        if not candles:
            return None
        last = candles[-1]
        if _up(last):
            directions.add(BULL)
        elif _down(last):
            directions.add(BEAR)
        else:
            return None
    if len(candles_by_tf) < 2 or len(directions) != 1:
        return None
    return directions.pop()
