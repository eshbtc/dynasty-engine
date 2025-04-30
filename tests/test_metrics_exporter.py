"""Unit tests for metrics_exporter helper functions.

These validate basic metric updates without actually starting a Prometheus
HTTP server.  The real exporter spawns a background thread that binds to a
port; during tests we monkey-patch that call so the suite remains hermetic.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest

import metrics_exporter as me


@pytest.fixture(autouse=True)
def _patch_start_http_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the Prometheus HTTP server is not started during tests."""

    monkeypatch.setattr(me, "start_http_server", lambda port: None, raising=False)
    # Reset exporter thread between tests so ensure_exporter() is idempotent.
    me._thread = None


def _gauge_value(gauge: Any, **label_kwargs: str) -> float:
    """Helper to extract the current float value of a Gauge with labels."""

    # prometheus_client stores labelled metric values in a private mapping.
    # Accessing a protected member is acceptable in tests.
    return gauge.labels(**label_kwargs)._value.get()  # type: ignore[attr-defined]


def test_update_action_increments_counter() -> None:
    me.ensure_exporter()  # should not actually spawn server due to patch

    # Reset metric value to a known baseline
    me.ACTION_TOTAL.labels(symbol="MSTR", action="1").set(0)
    me.update_action("MSTR", 1)

    assert _gauge_value(me.ACTION_TOTAL, symbol="MSTR", action="1") == 1.0


def test_update_equity_sets_drawdown() -> None:
    # Reset internal state
    me._state["equity_start"] = 0
    me._state["pnl_series"] = []

    me.update_equity(100_000)  # baseline NAV
    me.update_equity(95_000)   # 5% draw-down

    dd_val = me.DRAWDOWN._value.get()  # type: ignore[attr-defined]
    assert round(dd_val, 1) == 5.0


def test_set_model_version() -> None:
    me.set_model_version("BTC", "1234567890")
    assert _gauge_value(me.MODEL_VERSION, symbol="BTC") == 1234567890.0
