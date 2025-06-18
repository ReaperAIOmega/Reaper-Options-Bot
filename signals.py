from tradier_api import get_candles, get_quote
from strategy import *
from market import get_index_bias
from datetime import datetime, time
import random

def calculate_strike(price, direction="call"):
    # Round strike to nearest 5 for calls, 5 down for puts
    step = 5
    if direction == "call":
        return round(price / step) * step + step
    else:
        return round(price / step) * step - step

def score_signal(setup_names):
    # Basic scoring: +1 per valid setup detected
    score = 0
    scoring_details = []
    if "2-1-2_bullish" in setup_names:
        score += 2
        scoring_details.append("2-1-2 bullish")
    if "2-1-2_bearish" in setup_names:
        score += 2
        scoring_details.append("2-1-2 bearish")
    if "fvg_filled" in setup_names:
        score += 2
        scoring_details.append("FVG filled")
    if "failed_2u" in setup_names:
        score += 1
        scoring_details.append("Failed 2U")
    if "ftfc" in setup_names:
        score += 2
        scoring_details.append("FTFC alignment")
    return score, scoring_details

def generate_signals_for_symbol(symbol):
    signals = []
    candles_by_tf = {}
    for tf in ["120", "240", "D", "W"]:
        candles = get_candles(symbol, tf)
        if not candles:
            continue
        candles_by_tf[tf] = candles

    # Check multi-timeframe FTFC
    if not ftfc_alignment(candles_by_tf):
        return []

    setups_found = []
    # Check setups on 4h timeframe for example
    fourh_candles = candles_by_tf.get("240", [])
    if len(fourh_candles) >= 3:
        if is_2_1_2_bullish(fourh_candles[-3:]):
            setups_found.append("2-1-2_bullish")
        if is_2_1_2_bearish(fourh_candles[-3:]):
            setups_found.append("2-1-2_bearish")
        if failed_2u(fourh_candles[-3:]):
            setups_found.append("failed_2u")

    # Check FVG fill on daily
    daily_candles = candles_by_tf.get("D", [])
    if len(daily_candles) >= 3 and is_fvg_filled(daily_candles[-3], daily_candles[-2], daily_candles[-1]):
        setups_found.append("fvg_filled")

    if not setups_found:
        return []

    score, details = score_signal(setups_found)
    if score < 2:
        return []

    quote = get_quote(symbol)
    price = quote["last"]

    direction = "Call" if "2-1-2_bullish" in setups_found else "Put"

    strike = calculate_strike(price, "call" if direction == "Call" else "put")

    signal = {
        "symbol": symbol,
        "entry": round(price, 2),
        "strike": f"{strike}{direction[0]}",
        "expiry": "Weekly",
        "direction": direction,
        "score": score,
        "setups": details,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "reason": ", ".join(details)
    }
    signals.append(signal)
    return signals
