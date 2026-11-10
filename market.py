from tradier_api import get_quote

def get_index_bias():
    # Simple bias check for SPY and QQQ
    spy = get_quote("SPY")
    qqq = get_quote("QQQ")
    # Bullish if last price > open price for simplicity
    spy_bull = spy["last"] > spy["open"]
    qqq_bull = qqq["last"] > qqq["open"]
    if spy_bull and qqq_bull:
        return "bullish"
    elif not spy_bull and not qqq_bull:
        return "bearish"
    else:
        return "neutral"
