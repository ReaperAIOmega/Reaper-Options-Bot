from datetime import datetime

def is_inside_bar(c1, c2):
    # c2 is inside bar if high < c1.high and low > c1.low
    return c2["high"] < c1["high"] and c2["low"] > c1["low"]

def is_outside_bar(c1, c2, c3):
    # c2 engulfs c1 and c3: high > max(c1.high, c3.high) and low < min(c1.low, c3.low)
    high_range = max(c1["high"], c3["high"])
    low_range = min(c1["low"], c3["low"])
    return c2["high"] > high_range and c2["low"] < low_range

def is_2_1_2_bullish(candles):
    # Bullish continuation 2-1-2 pattern: c1 down, c2 inside, c3 breakout up
    if len(candles) < 3:
        return False
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]
    return (
        c1["close"] < c1["open"] and
        is_inside_bar(c1, c2) and
        c3["close"] > c2["high"]
    )

def is_2_1_2_bearish(candles):
    if len(candles) < 3:
        return False
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]
    return (
        c1["close"] > c1["open"] and
        is_inside_bar(c1, c2) and
        c3["close"] < c2["low"]
    )

def is_fvg(c1, c2):
    # Fair Value Gap basic check (gap between c1.low > c2.high)
    return c1["low"] > c2["high"]

def is_fvg_filled(c1, c2, c3):
    # Check if FVG gap is filled by c3
    return is_fvg(c1, c2) and c3["low"] <= c2["high"]

def failed_2u(candles):
    # Failed 2 Up pattern (bearish reversal after 2 up bars)
    if len(candles) < 3:
        return False
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]
    two_up = c1["close"] > c1["open"] and c2["close"] > c2["open"]
    failed = c3["close"] < c2["close"] and c3["open"] > c2["close"]
    return two_up and failed

def ftfc_alignment(candles_multi):
    # candles_multi = dict with timeframe keys: list of candles
    # Check trend direction consistency across timeframes (close > open = bullish)
    directions = []
    for timeframe, candles in candles_multi.items():
        if len(candles) < 1:
            continue
        last_candle = candles[-1]
        directions.append(1 if last_candle["close"] > last_candle["open"] else -1)
    if len(directions) < 2:
        return False
    return all(d == directions[0] for d in directions)

def get_market_structure_shift(candles):
    # Simplified: detect break of structure (BOS) or change of character (CHoCH)
    # For demo, check if last candle close breaks previous high or low
    if len(candles) < 3:
        return None
    prev_high = max(c["high"] for c in candles[:-1])
    prev_low = min(c["low"] for c in candles[:-1])
    last = candles[-1]
    if last["close"] > prev_high:
        return "BOS_up"
    if last["close"] < prev_low:
        return "BOS_down"
    return None
