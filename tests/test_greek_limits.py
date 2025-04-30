"""Tests for RiskManager greek exposure limits."""

from dyn_engine.risk_manager import RiskManager


def test_greek_exposure_limits():
    rm = RiskManager()
    rm.delta_limit = 1_000.0
    rm.vega_limit = 5_000.0

    # initial add within limits
    assert rm.add_greek_exposure(delta_change=200, vega_change=300) is False
    assert rm.net_delta == 200
    assert rm.net_vega == 300

    # still inside limits after second add
    assert rm.add_greek_exposure(delta_change=700, vega_change=4_000) is False
    assert rm.net_delta == 900
    assert rm.net_vega == 4_300

    # exceed delta limit
    assert rm.add_greek_exposure(delta_change=200, vega_change=100) is True
    # exceed vega limit separately
    rm2 = RiskManager()
    rm2.delta_limit = 10_000
    rm2.vega_limit = 1_000
    assert rm2.add_greek_exposure(delta_change=0, vega_change=1_200) is True
