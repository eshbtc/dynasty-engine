"""Build observation vectors for RL policy consistent with training features."""
from __future__ import annotations

from typing import Optional

import numpy as np

from data_provider import get_iv_rank, get_realized_vol  # existing utils
from greeks_utils import delta as bs_delta, vega as bs_vega

def _time_to_expiry(days_out: int = 7) -> float:
    """Return T in years for rough greek calc (weekly default)."""
    return days_out / 365.0

def build_obs(symbol: str, price: float, *, iv_rank: Optional[float] = None, volatility: Optional[float] = None) -> np.ndarray:
    """Return np.array suitable for TradingEnv obs.

    Currently env uses two features: price and iv_rank (or realized vol for crypto).
    This helper centralises the logic so live engine and back-tests stay consistent.
    """
    feature_2 = iv_rank if iv_rank is not None else volatility
    if feature_2 is None:
        # attempt fetch on-demand (avoid repeated network if possible by passing value)
        if symbol.upper() in ("BTC", "ETH"):
            feature_2 = get_realized_vol(symbol)
        else:
            feature_2 = get_iv_rank(symbol)
    if feature_2 is None:
        feature_2 = 0.0

    # Basic option greeks if we have IV estimate
    greeks = []
    if feature_2 and price:
        sigma = feature_2 / 100.0  # rough IV rank ~ pct vol? else pass explicit
        K = price  # ATM approximation
        T = _time_to_expiry()
        greeks = [bs_delta(price, K, T, 0.0, sigma), bs_vega(price, K, T, 0.0, sigma)]
    else:
        greeks = [0.0, 0.0]

    return np.array([price if price else 0.0, feature_2, *greeks], dtype=np.float32)
