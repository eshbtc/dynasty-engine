#!/usr/bin/env python3
"""Hyperparameter sweep using Optuna.

Run:
    python rl/hyperparam_search.py --csv data/mstr_features.parquet --symbol MSTR --trials 50
"""
from __future__ import annotations

import argparse
import os
import pickle

import optuna
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.evaluation import evaluate_policy
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from trading_env import TradingEnv
from model_registry import create_run_dir, save_metadata


# ------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Optuna PPO sweep")
    p.add_argument("--csv", required=True)
    p.add_argument("--symbol", required=True)
    p.add_argument("--trials", type=int, default=25)
    return p.parse_args()


# ------------------------------------------------------------------

def make_vec_env(df: pd.DataFrame, commission: float, slippage: float):
    def _make():
        env = TradingEnv(df)
        env.commission_bp = commission
        env.slippage_bp = slippage
        return env

    venv = DummyVecEnv([_make])
    return VecNormalize(venv, norm_obs=True, norm_reward=True)


# ------------------------------------------------------------------

def objective(trial: optuna.Trial, df: pd.DataFrame):
    n_steps = trial.suggest_int("n_steps", 128, 1024, step=128)
    batch_size = trial.suggest_int("batch_size", 128, 1024, step=128)
    gamma = trial.suggest_float("gamma", 0.9, 0.999)
    lr = trial.suggest_float("lr", 1e-5, 1e-3, log=True)

    commission = trial.suggest_float("commission", 0.5, 3.0)
    slippage = trial.suggest_float("slippage", 2.0, 10.0)

    env = make_vec_env(df, commission, slippage)
    model = PPO("MlpPolicy", env, n_steps=n_steps, batch_size=batch_size, gamma=gamma, learning_rate=lr, verbose=0)
    model.learn(total_timesteps=150_000)

    mean_reward, _ = evaluate_policy(model, env, n_eval_episodes=1)
    return mean_reward


# ------------------------------------------------------------------

def main():
    args = parse_args()
    df = pd.read_parquet(args.csv)

    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, df), n_trials=args.trials)
    print("Best params:", study.best_params)

    env = make_vec_env(df, study.best_params["commission"], study.best_params["slippage"])
    model = PPO(
        "MlpPolicy",
        env,
        n_steps=study.best_params["n_steps"],
        batch_size=study.best_params["batch_size"],
        gamma=study.best_params["gamma"],
        learning_rate=study.best_params["lr"],
        verbose=1,
    )
    model.learn(total_timesteps=300_000)

    run_dir = create_run_dir(args.symbol, tag="optuna")
    model.save(os.path.join(run_dir, "model"))
    with open(os.path.join(run_dir, "norm.pkl"), "wb") as f:
        pickle.dump(env, f)

    save_metadata(run_dir, study.best_params)
    print("Saved best model to", run_dir)


if __name__ == "__main__":
    main()
