"""Build observation vectors for RL policy consistent with training features."""
from __future__ import annotations

from typing import Optional

import numpy as np

from data_provider import get_iv_rank, get_realized_vol  # existing utils
from greeks_utils import delta as bs_delta, vega as bs_vega

def _time_to_expiry(days_out: int = 7) -> float:
    """Return T in years for rough greek calc (weekly default)."""
    return days_out / 365.0

def build_obs(symbol: str, price: float, *, iv_rank: Optional[float] = None, volatility: Optional[float] = None) -> Optional[np.ndarray]:
    """Return np.array suitable for TradingEnv obs. Logs and returns None if features are missing/invalid."""
    import logging
    logger = logging.getLogger(__name__)
    feature_2 = iv_rank if iv_rank is not None else volatility
    if feature_2 is None:
        # attempt fetch on-demand (avoid repeated network if possible by passing value)
        if symbol.upper() in ("BTC", "ETH"):
            feature_2 = get_realized_vol(symbol)
        else:
            feature_2 = get_iv_rank(symbol)
    if feature_2 is None or price is None or price == 0:
        logger.warning(f"[build_obs] Missing or invalid features for {symbol}: price={price}, feature_2={feature_2}. Skipping.")
        return None

    # Basic option greeks if we have IV estimate
    greeks = []
    if feature_2 and price:
        sigma = feature_2 / 100.0  # rough IV rank ~ pct vol? else pass explicit
        K = price  # ATM approximation
        T = _time_to_expiry()
        greeks = [bs_delta(price, K, T, 0.0, sigma), bs_vega(price, K, T, 0.0, sigma)]
    else:
        greeks = [0.0, 0.0]

    return np.array([price, feature_2, *greeks], dtype=np.float32)
