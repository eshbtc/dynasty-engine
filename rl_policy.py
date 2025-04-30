"""Load per-symbol RL models and output discrete action.
0 = HOLD, 1 = BUY, 2 = SELL
Models assumed to be stored under ./models/ppo_<symbol>.zip
"""
from __future__ import annotations

import os
import pickle
from typing import Dict, Any
from model_registry import latest_model_paths

import numpy as np
from stable_baselines3 import PPO

_policy_cache: Dict[str, PPO | None] = {}
_vec_norm: dict[str, Any] = {}


def get_rl_policy(symbol: str):
    import logging
    logger = logging.getLogger(__name__)
    symbol = symbol.lower()
    if symbol not in _policy_cache:
        try:
            model_path, norm_path = latest_model_paths(symbol)
            if model_path:
                _policy_cache[symbol] = PPO.load(model_path)
                if norm_path:
                    with open(norm_path, "rb") as f:
                        _vec_norm[symbol] = pickle.load(f)
            else:
                logger.warning(f"No model found for symbol {symbol}, defaulting to HOLD")
                _policy_cache[symbol] = None
        except Exception as e:
            logger.error(f"Error loading RL policy for {symbol}: {e}")
            _policy_cache[symbol] = None
    return _policy_cache[symbol]


def decide(symbol: str, obs: np.ndarray) -> int:
    """Return action 0/1/2 given observation array (1D)."""
    import logging
    logger = logging.getLogger(__name__)
    model = get_rl_policy(symbol)
    if symbol in _vec_norm:
        obs = _vec_norm[symbol].observation_space.filter(obs)
    if model is None:
        logger.info(f"No RL model for {symbol}, returning HOLD (0)")
        return 0  # default HOLD if no model
    try:
        action, _state = model.predict(obs, deterministic=True)
        return int(action)
    except Exception as e:
        logger.error(f"RL model prediction error for {symbol}: {e}")
        return 0
