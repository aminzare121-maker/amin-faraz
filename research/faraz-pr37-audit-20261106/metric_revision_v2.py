"""Isolated numeric-statistics fix; never imported by locked v1 or operational code."""
ZERO_TOLERANCE_USD=1e-9

def snap_net(pnl):
    """Missing outcomes stay missing; only sub-nanodollar residuals become zero."""
    if pnl is None:return None
    return 0.0 if abs(pnl)<=ZERO_TOLERANCE_USD else pnl
