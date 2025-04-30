"""Gymnasium environment for single-symbol trading with discrete actions.

Observation = numpy array [price, iv_rank]
Action      = 0 HOLD, 1 BUY (long), 2 SELL (flat → cash)
We model a single position (long only) for simplicity.
Reward      = change in Net Asset Value between steps.

Usage:
    df = pd.read_csv("mstr_features.csv")
    env = TradingEnv(df)
    obs, _ = env.reset()
    ...
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import gymnasium as gym


# Helper -----------------------------------------------------------------
def _calc_cost(notional: float, commission_bp: float, slippage_bp: float) -> float:
    """Return dollar cost for given notional trade."""
    return notional * (commission_bp + slippage_bp) / 10000.0


class TradingEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, df: pd.DataFrame):
        if not {"price", "iv_rank"}.issubset(df.columns):
            raise ValueError("DataFrame must contain 'price' and 'iv_rank' columns")

        self.df = df.reset_index(drop=True)
        self.action_space = gym.spaces.Discrete(3)  # 0 hold,1 long,2 short/flat toggle
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(2,), dtype=np.float32)

        # Configurable parameters
        self.starting_cash = 1_000_000.0
        self.commission_bp: float = 1.0  # 1 bp commission
        self.slippage_bp: float = 5.0     # 5 bp slippage
        self.allow_short: bool = False

        # Internal state
        self._idx: int = 0
        self._pos_qty: float = 0.0  # positive long, negative short
        self._cash: float = self.starting_cash
        self._prev_nav: float = self.starting_cash

    # ---------------------------------------------------------------------
    def _get_obs(self):
        row = self.df.iloc[self._idx]
        return np.array([row["price"], row["iv_rank"]], dtype=np.float32)

    # ---------------------------------------------------------------------
    def reset(self, *, seed=None, options=None):  # noqa: D401
        super().reset(seed=seed)
        self._idx = 0
        self._pos_qty = 0.0
        self._cash = self.starting_cash
        self._prev_nav = self.starting_cash
        return self._get_obs(), {}

    # ---------------------------------------------------------------------
    def step(self, action: int):
        price = float(self.df.loc[self._idx, "price"])

        # Determine target position based on action
        target_pos = self._pos_qty
        if action == 1:  # Long
            target_pos = self._cash / price  # fully long
        elif action == 2:
            if self.allow_short:
                target_pos = -self._cash / price  # fully short
            else:
                # Flat (close long) if currently long else hold
                target_pos = 0.0

        # Execute trade difference
        delta_qty = target_pos - self._pos_qty
        if delta_qty != 0:
            notional = abs(delta_qty) * price
            cost = _calc_cost(notional, self.commission_bp, self.slippage_bp)
            self._cash -= notional + cost if delta_qty > 0 else -notional - cost  # buy reduces cash, sell increases
            self._pos_qty = target_pos

        # Advance time
        self._idx += 1
        terminated = self._idx >= len(self.df) - 1
        next_price = float(self.df.loc[self._idx, "price"]) if not terminated else price
        nav = self._cash + self._pos_qty * next_price
        reward = nav - self._prev_nav  # incremental reward
        self._prev_nav = nav
        return self._get_obs(), reward, terminated, False, {}

    # ---------------------------------------------------------------------
    def render(self, mode="human"):
        price = float(self.df.loc[self._idx, "price"])
        nav = self._cash + self._pos_qty * price
        print(f"Step {self._idx}: price={price:.2f} nav={nav:.2f} pos={self._pos_qty:.4f}")

    def close(self):
        pass
