"""Prometheus metrics and helpers (Phase-4 Observability)."""
from __future__ import annotations

from typing import Optional

from prometheus_client import Gauge, Counter, Histogram, start_http_server

# --- Metric definitions ----------------------------------------------------

drawdown_gauge = Gauge(
    "dynasty_drawdown_pct", "Current account drawdown percentage"
)

health_gauge = Gauge(
    "dynasty_health_status", "Health status of the Dynasty Engine (1=OK, 0=Error)"
)

trade_counter = Counter(
    "dynasty_trade_total", "Trades executed", ["kind", "status"]
)
trade_fee_total = Counter(
    "dynasty_trade_fee_total", "Total commissions paid (USD)"
)
trade_slippage_hist = Histogram(
    "dynasty_trade_slippage_bp",
    "Trade slippage (basis-points)",
    buckets=[-50, -20, -10, -5, -1, 0, 1, 5, 10, 20, 50, 100, 200],
)
error_counter = Counter("dynasty_error_total", "Errors", ["module"])

# Latency histograms
eval_assets_latency = Histogram(
    "dynasty_eval_assets_latency_seconds", "evaluate_assets cycle duration (s)")
eval_hedges_latency = Histogram(
    "dynasty_eval_hedges_latency_seconds", "evaluate_hedges cycle duration (s)")


# --- Initialisation --------------------------------------------------------

_started: bool = False


def init_metrics(port: int) -> None:
    """Start Prometheus HTTP server once (idempotent)."""
    global _started
    if _started:
        return
    try:
        start_http_server(port)
    except OSError:
        # Already running (likely started elsewhere)
        pass
    _started = True


# --- Helper functions ------------------------------------------------------

def record_trade(kind: str, status: str, commission: float, slippage_bp: float | None) -> None:
    status_u = status.upper()
    trade_counter.labels(kind=kind, status=status_u).inc()
    trade_fee_total.inc(max(commission, 0.0))
    if slippage_bp is not None:
        trade_slippage_hist.observe(slippage_bp)


def record_error(module: str) -> None:
    error_counter.labels(module=module).inc()


# ---------- Decorators -----------------------------------------------------

import time
from functools import wraps


def observe_latency(hist: Histogram):
    """Decorator to observe async function latency in provided histogram."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                hist.observe(time.perf_counter() - start)

        return wrapper

    return decorator


# ---------- Simple Health Endpoint ----------------------------------------

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def start_health_server(port: int = 8001):
    """Start simple /health HTTP endpoint in background daemon thread."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/health", "/ready"):
                self.send_response(404)
                self.end_headers()
                return

            status = "ok" if health_gauge._value.get() == 1 else "error"
            payload = json.dumps({"status": status}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):  # Quiet server logs
            return

    def _serve():
        try:
            httpd = HTTPServer(("", port), _Handler)
            httpd.serve_forever()
        except OSError:
            pass  # Port in use

    threading.Thread(target=_serve, daemon=True).start()
