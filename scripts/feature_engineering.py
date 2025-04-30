#!/usr/bin/env python3
"""Add derived features and clean raw price file.

Usage:
    python scripts/feature_engineering.py --in data/mstr_raw.parquet --out data/mstr_features.parquet

Creates:
    price_return     daily pct change
    price_z          z-score of price over 30-day window
    iv_rank_filled   forward-fill iv_rank then 252-day percentile rank
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


# ------------------------------------------------------------------

def parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Feature engineering for RL training")
    p.add_argument("--in", dest="inp", required=True, help="Input parquet path (raw)")
    p.add_argument("--out", required=True, help="Output parquet path (features)")
    return p.parse_args()


# ------------------------------------------------------------------

def main() -> None:
    args = parse()
    df = pd.read_parquet(args.inp)
    df = df.sort_values("date").reset_index(drop=True)

    # Returns
    df["price_return"] = df["price"].pct_change().fillna(0.0)

    # 30-day z-score of price
    df["price_z"] = (df["price"] - df["price"].rolling(30).mean()) / df["price"].rolling(30).std()
    df["price_z"].fillna(0.0, inplace=True)

    # Fill iv_rank; if still nan fallback to 50
    df["iv_rank_filled"] = df["iv_rank"].fillna(method="ffill").fillna(50)
    df["iv_rank_filled"] = df["iv_rank_filled"].rolling(252).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1]*100, raw=False)
    df["iv_rank_filled"].fillna(method="bfill", inplace=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Wrote features to {out} – {len(df)} rows")


if __name__ == "__main__":
    main()
