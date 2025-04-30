"""Summarize daily episode logs for backtesting and monitoring."""
from __future__ import annotations

import pandas as pd
from pathlib import Path
from typing import Tuple

_EP_FILE = Path("data/trades_episodes.csv")
_OUT_FILE = Path("data/daily_summary.parquet")


def _load() -> pd.DataFrame:
    if not _EP_FILE.exists():
        raise SystemExit("Episode log missing")
    return pd.read_csv(_EP_FILE)


def summarize_day(df: pd.DataFrame) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["ts"], unit="s").dt.date
    grp = df.groupby(["date", "symbol"]).agg(
        trades=("action", "count"),
        buys=("action", lambda x: (x == 1).sum()),
        sells=("action", lambda x: (x == 2).sum()),
        last_price=("price", "last"),
        feature2_last=("feature2", "last"),
    )
    grp.reset_index(inplace=True)
    return grp


def main():
    df = _load()
    daily = summarize_day(df)
    _OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(_OUT_FILE, index=False)
    print("Wrote summary rows:", len(daily))


if __name__ == "__main__":
    main()
