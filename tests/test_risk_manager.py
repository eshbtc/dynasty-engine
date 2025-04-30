"""Tests for RiskManager update_and_check."""

from dyn_engine.risk_manager import RiskManager


def test_drawdown_and_manual_halt(monkeypatch):
    rm = RiskManager()
    rm.drawdown_limit_pct = 5.0

    # Start with equity 100k – should record as max
    halt, dd = rm.update_and_check(100_000)
    assert not halt and dd == 0
    assert rm.max_equity == 100_000

    # Equity drops to 95k (5% drawdown) -> halt
    halt, dd = rm.update_and_check(95_000)
    assert halt and round(dd, 1) == 5.0

    # Manual halt environment flag
    monkeypatch.setenv("DYNASTY_HALT", "true")
    halt2, _ = rm.update_and_check(96_000)
    assert halt2
