"""ExecutionService – unified trade execution API (Phase-3).

Wraps `OrderHelper` (Interactive Brokers) and exposes a coroutine method
`execute_trade()` returning a dataclass with structured result & fee/slippage.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from ib_insync import IB, Contract

from order_helper import OrderHelper
from dyn_engine.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TradeResult:
    status: str
    avg_fill_price: float
    commission: float
    slippage_bp: float


class ExecutionService:
    """High-level async execution helper wrapping OrderHelper."""

    def __init__(self, ib: IB):
        if not ib or not ib.isConnected():
            raise ValueError("ExecutionService requires connected IB instance")
        self.ib = ib
        self.helper = OrderHelper(ib)

    async def execute_trade(
        self, contract: Contract, action: str, quantity: int
    ) -> TradeResult:
        """Market-order execution with slippage estimation using mid-price."""
        from settings import get_settings
        cfg = get_settings()
        try:
            if cfg.paper_trade:
                logger.info(
                    "[PAPER] %s %s qty=%d – no live order sent", action, contract.symbol, quantity
                )
                # Use mid=0 to indicate placeholder; real analytics can still estimate PnL later
                return TradeResult(status="PAPER", avg_fill_price=0.0, commission=0.0, slippage_bp=0.0)

            # Request snapshot market data for mid price
            md = self.ib.reqMktData(contract, "", False, False)
            await asyncio.sleep(1)  # wait for data
            mid_price: float | None = None
            if md.bid and md.ask and md.bid > 0 and md.ask > 0:
                mid_price = (md.bid + md.ask) / 2
            elif md.last and md.last > 0:
                mid_price = md.last
            else:
                logger.warning("Could not obtain mid price; defaulting to 0.0 for slippage calc")
                mid_price = 0.0
            self.ib.cancelMktData(contract)

            result_dict = await self.helper.execute_trade_async(
                contract, action, quantity, mid_price
            )
            return TradeResult(**result_dict)
        except Exception as e:
            logger.error(f"Exception in execute_trade: {e}")
            return TradeResult(status="Failed", avg_fill_price=0.0, commission=0.0, slippage_bp=0.0)

    async def execute_multi_leg_trade(
        self, contracts: list, actions: list, quantities: list
    ) -> list[TradeResult]:
        """
        Execute a multi-leg trade (e.g., spreads, covered calls).
        contracts: list of IBKR Contract objects
        actions: list of 'BUY' or 'SELL' strings (same length)
        quantities: list of ints (same length)
        Returns list of TradeResult objects.
        """
        results = []
        for i, (contract, action, qty) in enumerate(zip(contracts, actions, quantities)):
            logger.info(f"[Multi-Leg] Executing leg {i+1}/{len(contracts)}: {action} {qty} {getattr(contract, 'symbol', str(contract))}")
            try:
                result = await self.execute_trade(contract, action, qty)
                results.append(result)
            except Exception as e:
                logger.error(f"[Multi-Leg] Error executing leg {i+1}: {e}")
                results.append(TradeResult(status="Failed", avg_fill_price=0.0, commission=0.0, slippage_bp=0.0))
        logger.info(f"[Multi-Leg] Trade results: {[r.status for r in results]}")
        return results


# --- Singleton helper -------------------------------------------------------
_exec_service: Optional[ExecutionService] = None


def get_execution_service(ib: IB) -> ExecutionService:
    global _exec_service
    if _exec_service is None or _exec_service.ib is not ib:
        _exec_service = ExecutionService(ib)
    return _exec_service
