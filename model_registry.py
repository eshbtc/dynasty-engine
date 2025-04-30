"""Utility functions for storing and retrieving RL models with versioning."""
from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Dict, Tuple, Optional


def _symbol_dir(symbol: str) -> str:
    return os.path.join("models", symbol.lower())


def create_run_dir(symbol: str, tag: str = "run") -> str:
    """Create directory like models/<sym>/<YYYYmmdd_HHMMSS>_<tag>."""
    ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(_symbol_dir(symbol), f"{ts}_{tag}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def save_metadata(run_dir: str, meta: Dict[str, Any]):
    meta_path = os.path.join(run_dir, "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def latest_model_paths(symbol: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (model.zip, norm.pkl) paths for most recent run, or (None, None)."""
    root = _symbol_dir(symbol)
    if not os.path.isdir(root):
        return None, None
    dirs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    if not dirs:
        return None, None
    dirs.sort(reverse=True)  # lexicographic order works due to timestamp prefix
    latest = os.path.join(root, dirs[0])
    model_p = os.path.join(latest, "model.zip")
    norm_p = os.path.join(latest, "norm.pkl")
    return model_p if os.path.exists(model_p) else None, norm_p if os.path.exists(norm_p) else None
