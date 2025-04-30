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
        # Expanded action space for multi-strategy RL
        # 0: HOLD
        # 1: BUY stock (long)
        # 2: SELL stock (flat/short)
        # 3: ENTER bull call spread
        # 4: EXIT bull call spread
        # 5: ENTER bear put spread
        # 6: EXIT bear put spread
        # 7: ENTER covered call
        # 8: EXIT covered call
        # 9: ENTER crypto futures long
        # 10: EXIT crypto futures long
        # 11: ENTER stop-loss
        # 12: ENTER take-profit
        # (Add more as needed)
        self.action_space = gym.spaces.Discrete(13)
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
        import random
        super().reset(seed=seed)
        if options and options.get('random_start', False):
            self._idx = random.randint(0, max(0, len(self.df)-2))
        else:
            self._idx = 0
        self._pos_qty = 0.0
        self._cash = self.starting_cash
        self._prev_nav = self.starting_cash
        return self._get_obs(), {}

    # ---------------------------------------------------------------------
    def step(self, action: int):
        import logging
        logger = logging.getLogger(__name__)
        # --- Bounds check ---
        if self._idx >= len(self.df):
            logger.error(f"Index {self._idx} out of bounds for df of length {len(self.df)}")
            raise IndexError("Step called past end of episode")
        price = float(self.df.loc[self._idx, "price"])
        iv_rank = float(self.df.loc[self._idx, "iv_rank"])
        # --- NaN/Inf check ---
        if not np.isfinite(price) or not np.isfinite(iv_rank):
            logger.warning(f"NaN/Inf in price ({price}) or iv_rank ({iv_rank}) at idx {self._idx}")
            reward = -1.0
            done = True
            info = {"error": "NaN/Inf in data"}
            return self._get_obs(), reward, done, False, info
        # --- Multi-strategy action logic scaffold ---
        target_pos = self._pos_qty
        # Stock long/short
        if action == 1:  # BUY stock (long)
            if price <= 0:
                logger.warning(f"Attempted BUY with non-positive price {price} at idx {self._idx}")
                target_pos = self._pos_qty
            else:
                target_pos = self._cash / price
            logger.info(f"Action BUY: target_pos={target_pos}")
        elif action == 2:  # SELL stock (flat/short)
            if self.allow_short:
                if price <= 0:
                    logger.warning(f"Attempted SHORT with non-positive price {price} at idx {self._idx}")
                    target_pos = self._pos_qty
                else:
                    target_pos = -self._cash / price
                logger.info(f"Action SHORT: target_pos={target_pos}")
            else:
                target_pos = 0.0
                logger.info(f"Action SELL (flat): target_pos={target_pos}")
        # Bull call spread
        elif action == 3:  # ENTER bull call spread
            logger.warning("ENTER bull call spread not implemented")
            raise NotImplementedError("Bull call spread logic not implemented")
        elif action == 4:  # EXIT bull call spread
            logger.warning("EXIT bull call spread not implemented")
            raise NotImplementedError("Exit bull call spread logic not implemented")
        # Bear put spread
        elif action == 5:  # ENTER bear put spread
            logger.warning("ENTER bear put spread not implemented")
            raise NotImplementedError("Bear put spread logic not implemented")
        elif action == 6:  # EXIT bear put spread
            logger.warning("EXIT bear put spread not implemented")
            raise NotImplementedError("Exit bear put spread logic not implemented")
            pass
        # Covered call
        elif action == 7:  # ENTER covered call
            pass
        elif action == 8:  # EXIT covered call
            pass
        # Crypto futures
        elif action == 9:  # ENTER crypto futures long
            pass
        elif action == 10:  # EXIT crypto futures long
            pass
        # Stop-loss / Take-profit (can be implemented as flags or triggers)
        elif action == 11:  # ENTER stop-loss
            pass
        elif action == 12:  # ENTER take-profit
            pass
        # --- End multi-strategy scaffold ---

        # Execute trade difference (for stock, extend for other instruments)
        delta_qty = target_pos - self._pos_qty
        if delta_qty != 0:
            notional = abs(delta_qty) * price
            cost = _calc_cost(notional, self.commission_bp, self.slippage_bp)
            self._cash -= notional + cost if delta_qty > 0 else -notional - cost
            self._pos_qty = target_pos

        # Advance time
        self._idx += 1
        terminated = self._idx >= len(self.df) - 1
        next_price = float(self.df.loc[self._idx, "price"]) if not terminated else price
        nav = self._cash + self._pos_qty * next_price

        # --- Reward shaping for 5% monthly profit targeting ---
        # Example: reward = 1 if NAV increased by >5% in a month, else penalize
        # (Implement rolling window logic as needed)
        reward = nav - self._prev_nav  # incremental reward (default)
        self._prev_nav = nav
        # Optionally: add custom reward logic here

        return self._get_obs(), reward, terminated, False, {}

    # ---------------------------------------------------------------------
    def render(self, mode="human"):
        price = float(self.df.loc[self._idx, "price"])
        nav = self._cash + self._pos_qty * price
        print(f"Step {self._idx}: price={price:.2f} nav={nav:.2f} pos={self._pos_qty:.4f}")

    def close(self):
        pass
