"""Lightweight CSV-based episode logger for live RL trading steps."""
from __future__ import annotations

import csv
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np

_LOG_PATH = Path("data/trades_episodes.csv")
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_HEADERS = [
    "ts",  # unix epoch seconds
    "symbol",
    "action",  # 0 hold 1 buy 2 sell
    "price",
    "feature2",  # iv_rank or vol
    "nav",  # optional
]

# --- Option trade CSV ---
_OPT_PATH = Path("data/option_trades.csv")
_OPT_HEADERS = [
    "ts",
    "symbol",
    "right",  # C / P
    "strike",
    "expiry",
    "side",  # BUY / SELL
    "qty",
    "fill_price",
]


def _ensure_file():
    if not _LOG_PATH.exists():
        with open(_LOG_PATH, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(_HEADERS)


def _ensure_opt_file():
    if not _OPT_PATH.exists():
        with open(_OPT_PATH, "w", newline="") as f:
            csv.writer(f).writerow(_OPT_HEADERS)


def log_step(
    symbol: str,
    action: int,
    price: float,
    feature2: float,
    nav: Optional[float] = None,
):
    """Append a single trading step to the CSV."""
    _ensure_file()
    row = [
        int(time.time()),
        symbol.upper(),
        int(action),
        round(price, 4) if price else 0.0,
        round(feature2, 4),
        round(nav, 2) if nav is not None else "",
    ]
    with open(_LOG_PATH, "a", newline="") as f:
        csv.writer(f).writerow(row)


def log_option_trade(
    symbol: str,
    right: str,
    strike: float,
    expiry: str,
    side: str,
    qty: int,
    fill_price: float,
):
    """Log executed option trade legs for audit / back-test reconstruction."""
    _ensure_opt_file()
    ts = int(time.time())
    with open(_OPT_PATH, "a", newline="") as f:
        csv.writer(f).writerow([
            ts,
            symbol.upper(),
            right.upper(),
            round(strike, 2),
            expiry,
            side.upper(),
            int(qty),
            round(fill_price, 4),
        ])
