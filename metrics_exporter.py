"""Expose Prometheus metrics for live RL trading system."""
from __future__ import annotations

import time
import json
import os
from threading import Thread
from typing import Dict

from prometheus_client import start_http_server, Gauge

# Gauges
SHARPE = Gauge("dynasty_sharpe", "Live rolling sharpe ratio")
DRAWDOWN = Gauge("dynasty_drawdown_pct", "Current drawdown %")
ACTION_TOTAL = Gauge("dynasty_action_total", "Total actions by type", labelnames=["symbol", "action"])
MODEL_VERSION = Gauge("dynasty_model_version", "Model version timestamp", labelnames=["symbol"])
RL_INFER_MS = Gauge("dynasty_rl_infer_ms", "PPO inference latency ms", labelnames=["symbol"])

_state: Dict[str, float] = {
    "equity_start": 0.0,
    "equity_now": 0.0,
    "pnl_history": 0.0,
}

_PUSH_FILE = os.path.join(os.path.dirname(__file__), "data", "device_tokens.json")

def _load_tokens():
    if os.path.exists(_PUSH_FILE):
        try:
            return json.load(open(_PUSH_FILE))
        except Exception:
            return []
    return []

def send_push(body: str):
    # Simple Expo push without external deps (curl Expo). Good for internal use.
    tokens = [d["token"] for d in _load_tokens()]
    if not tokens:
        return
    import requests, logging

    logger = logging.getLogger(__name__)

    for t in tokens:
        retry = 0
        delay = 1.0  # start at 1 s
        while retry < 3:
            try:
                requests.post(
                    "https://exp.host/--/api/v2/push/send",
                    json={"to": t, "title": "Dynasty", "body": body},
                    timeout=4,
                )
                break  # success -> next token
            except Exception as exc:
                retry += 1
                logger.warning("Expo push failure (%s). Retry %d/3", exc, retry)
                time.sleep(delay)
                delay *= 2  # exponential backoff
        else:
            logger.error("Expo push totally failed for token %s", t)


def update_action(symbol: str, action: int):
    ACTION_TOTAL.labels(symbol=symbol, action=str(action)).inc()


def update_equity(nav: float):
    if _state["equity_start"] == 0:
        _state["equity_start"] = nav
    _state["equity_now"] = nav
    dd = 100 * (1 - nav / _state["equity_start"])
    DRAWDOWN.set(dd)

    # naive sharpe on cumulative pnl; improve later
    pnl = nav - _state["equity_start"]
    _state.setdefault("pnl_series", []).append(pnl)
    if len(_state["pnl_series"]) > 50:
        import numpy as np

        series = np.diff(_state["pnl_series"][-50:])
        if series.std() > 0:
            sharpe = series.mean() / series.std() * (252**0.5)
            SHARPE.set(sharpe)


def set_model_version(symbol: str, timestamp: str):
    MODEL_VERSION.labels(symbol=symbol).set(float(timestamp))


def record_rl_latency(symbol: str, latency_ms: float) -> None:
    """Update RL inference latency gauge."""
    RL_INFER_MS.labels(symbol=symbol).set(latency_ms)


# -------- server thread --------

def _serve():
    start_http_server(8000)
    while True:
        time.sleep(60)


_thread: Thread | None = None


def ensure_exporter():
    global _thread
    if _thread is None:
        _thread = Thread(target=_serve, daemon=True)
        _thread.start()
