"""Unit tests for ExecutionService using stubbed IB and OrderHelper."""

import pytest
from types import SimpleNamespace

# We import the module under test after patching


class _StubMarketData(SimpleNamespace):
    bid: float = 100.0
    ask: float = 102.0
    last: float = 101.0


class _StubIB:
    """Very small subset of ib_insync.IB interface required for our tests."""

    def isConnected(self) -> bool:
        return True

    def reqMktData(self, contract, *args, **kwargs):  # noqa: D401
        return _StubMarketData()

    def cancelMktData(self, contract):  # noqa: D401
        return None


@pytest.mark.asyncio
async def test_execute_trade(monkeypatch):
    """execute_trade should return TradeResult from stubbed OrderHelper."""

    async def _fast_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr("asyncio.sleep", _fast_sleep)

    # Patch OrderHelper with stub implementation inside module
    from dyn_engine import execution as exec_mod

    class _StubOH:
        async def execute_trade_async(self, contract, action, quantity, mid_price):  # noqa: D401
            # Return dict matching TradeResult fields
            return {
                "status": "Filled",
                "avg_fill_price": 101.0,
                "commission": 0.5,
                "slippage_bp": 2.0,
            }

    monkeypatch.setattr(exec_mod, "OrderHelper", _StubOH)

    ib = _StubIB()
    svc = exec_mod.ExecutionService(ib)
    result = await svc.execute_trade(contract=object(), action="BUY", quantity=1)

    assert result.status == "Filled"
    assert result.avg_fill_price == 101.0
    assert result.commission == 0.5
    assert result.slippage_bp == 2.0
