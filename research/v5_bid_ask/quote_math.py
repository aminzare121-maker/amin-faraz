"""Executability-correct quote calculations for XAUUSD (Bid OHLC and spread in USD/oz)."""
def executable_close(side,bid_close,spread_usd):
    if side not in (-1,1):raise ValueError("side must be -1 or +1")
    if spread_usd<0:raise ValueError("negative spread")
    return bid_close if side==1 else bid_close+spread_usd

def closed_bar_profit_per_oz(side,bid_close,spread_usd,entry_price):
    return side*(executable_close(side,bid_close,spread_usd)-entry_price)

def trailing_candidate(side,bid_close,spread_usd,trail_distance):
    if trail_distance<=0:raise ValueError("trail_distance must be positive")
    return executable_close(side,bid_close,spread_usd)-side*trail_distance
