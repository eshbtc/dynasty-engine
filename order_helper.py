"""Centralised execution helper.
Choose between immediate‑or‑cancel LIMIT and simple VWAP‑slice.
Adds `commission` estimate (0.35 ¢/share US stocks, 0.05 % notional crypto).
"""
from ib_insync import *
import math, time
import asyncio # Import asyncio
import logging # Import logging

# Get a logger for this module
logger = logging.getLogger(__name__)

FEE_PER_SHARE = 0.0035     # USD
CRYPTO_FEE_BP = 5           # basis‑points

class OrderHelper:
    def __init__(self, ib: IB):
        self.ib = ib
        if not ib or not ib.isConnected():
            # Log a warning or raise an error if IB connection is not provided or inactive
            logger.warning("OrderHelper initialized without an active IB connection.") # <-- Use logger
            # raise ValueError("OrderHelper requires an active IB connection.")
        else:
             logger.info("OrderHelper initialized with active IB connection.") # <-- Use logger

    async def execute_trade_async(self, contract: Contract, action: str, quantity: int, mid_price: float):
        """Executes a trade asynchronously using a Market Order and returns execution details. Retries up to 3 times if failed."""
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            if not self.ib.isConnected():
                logger.error(f"IB connection lost. Cannot place order. Attempt {attempt}/{max_attempts}")
                if attempt == max_attempts:
                    return {'status': 'Failed', 'avg_fill_price': 0.0, 'commission': 0.0, 'slippage_bp': 0.0}
                await self.ib.sleep(2)
                continue

            order = MarketOrder(action, quantity)
            trade = self.ib.placeOrder(contract, order)
            logger.info(f"Placed Market Order: {action} {quantity} {contract.symbol} (Attempt {attempt}/{max_attempts})")

            # --- Wait for terminal state --- Wait up to 60 seconds
            start_time = time.time()
            while trade.isActive() and (time.time() - start_time < 60):
                await self.ib.sleep(1)

            if trade.isDone():
                avg_fill_price = trade.orderStatus.avgFillPrice
                commission = trade.commissionReport.commission if trade.commissionReport else 0.0
                status = trade.orderStatus.status

                # Calculate slippage against the mid-price at the time of decision
                slippage = 0.0
                if mid_price and mid_price > 0 and avg_fill_price and avg_fill_price > 0:
                    if action == 'BUY':
                        slippage = avg_fill_price - mid_price
                    elif action == 'SELL':
                        slippage = mid_price - avg_fill_price
                    slippage_bp = (slippage / mid_price) * 10000
                else:
                    slippage_bp = 0.0

                logger.info(f"Trade Done. Status: {status}, Fill Price: {avg_fill_price:.2f}, Mid Price: {mid_price:.2f}, Slippage: {slippage:.2f} ({slippage_bp:.2f} bp), Commission: {commission:.2f}")
                return {'status': status, 'avg_fill_price': avg_fill_price, 'commission': commission, 'slippage_bp': slippage_bp}
            else:
                status = trade.orderStatus.status
                logger.warning(f"Trade did not complete successfully. Status: {status} (Attempt {attempt}/{max_attempts})")
                if trade.isActive():
                    self.ib.cancelOrder(trade.order)
                    logger.info(f"Attempted to cancel order {trade.order.orderId}")
                if attempt == max_attempts:
                    return {'status': status, 'avg_fill_price': 0.0, 'commission': 0.0, 'slippage_bp': 0.0}
                await self.ib.sleep(2)
        # Should never reach here
        logger.error(f"Trade execution failed after {max_attempts} attempts.")
        return {'status': 'Failed', 'avg_fill_price': 0.0, 'commission': 0.0, 'slippage_bp': 0.0}


    # --- Original limit_or_vwap (can be kept for reference or adapted/removed) ---
    # Note: This synchronous version is not suitable for the async main loop
    # def limit_or_vwap(self, contract: Contract, quantity: int, limit_offset: float = 0.003):
    #     md = self.ib.reqMktData(contract, '', False, False)
    #     time.sleep(0.5) # Synchronous sleep
    #     mid = (md.bid + md.ask)/2 if md.bid and md.ask else md.last
    #     if not mid:
    #         return None, 0.0, 0.0 # Returning price, fee, slippage
    #     px = round(mid * (1+limit_offset), 2)
    #     order = LimitOrder('BUY', quantity, px, tif='IOC')
    #     trade = self.ib.placeOrder(contract, order)
    #     filled = trade.orderStatus.filled
    #     # This needs async adaptation to wait for trade status properly
    #     # ... (VWAP fallback logic needs async rewrite) ...
    #     fee = quantity*FEE_PER_SHARE if contract.secType=='STK' else (contract.currency=='USD' and (quantity*px*CRYPTO_FEE_BP/1e4))
    #     # Original slippage calc was based on intended price, not fill price
    #     slippage_bp = (px-mid)/mid*10000 if mid else 0.0
    #     return px, fee, slippage_bp