#!/usr/bin/env python3
"""Train a PPO agent on historical feature data.

CSV must contain at minimum:
    date, price, iv_rank
Additional columns can be ignored by the env; extend trading_env.py to use them.

Example:
    python train_rl.py --csv data/mstr_features.csv --symbol MSTR --timesteps 500000
This will write the model to ./models/ppo_mstr.zip and can immediately be used
by the live engine via rl_policy.py.
"""
from __future__ import annotations

import argparse
import os
from typing import Any

import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from model_registry import create_run_dir, save_metadata
from trading_env import TradingEnv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train PPO trading agent")
    parser.add_argument("--csv", required=True, help="CSV file with price / iv_rank columns")
    parser.add_argument("--symbol", required=True, help="Ticker symbol (e.g., MSTR)")
    parser.add_argument("--timesteps", type=int, default=200_000, help="Total training timesteps")
    parser.add_argument("--commission", type=float, default=1.0, help="Commission in bp")
    parser.add_argument("--slippage", type=float, default=5.0, help="Slippage in bp")
    parser.add_argument("--allow-short", action="store_true", help="Enable short selling in env")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.csv)
    if not {"price", "iv_rank"}.issubset(df.columns):
        raise ValueError("CSV must contain 'price' and 'iv_rank' columns")

    def make_env():
        env = TradingEnv(df)
        env.commission_bp = args.commission
        env.slippage_bp = args.slippage
        env.allow_short = args.allow_short
        return env

    env = DummyVecEnv([make_env])
    env = VecNormalize(env, norm_obs=True, norm_reward=True)

    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=args.lr,
        gamma=args.gamma,
        n_steps=256,
        batch_size=256,
        verbose=1,
    )

    model.learn(total_timesteps=args.timesteps)

    # ---------------- save -----------------
    run_dir = create_run_dir(args.symbol, tag="manual")
    model.save(os.path.join(run_dir, "model"))
    with open(os.path.join(run_dir, "norm.pkl"), "wb") as f:
        pickle.dump(env, f)

    save_metadata(
        run_dir,
        {
            "timesteps": args.timesteps,
            "commission_bp": args.commission,
            "slippage_bp": args.slippage,
            "allow_short": args.allow_short,
            "lr": args.lr,
            "gamma": args.gamma,
        },
    )

    print(f"Model saved to {run_dir}")


if __name__ == "__main__":
    main()
