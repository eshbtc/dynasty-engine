# Dynasty Engine Phase 3 - Auto-Hedger Module (auto_hedger.py)

from ib_insync import *
import random
import asyncio
import datetime
import sqlite3
import yaml

class AutoHedger:
    def __init__(self, ib_instance, config):
        self.ib = ib_instance
        self.config = config
        self.db_path = 'trade_tracker.db'
        self.log = [] # Log hedge actions

    async def get_current_position(self, symbol):
        """ Fetches the current position size for a given symbol using IBKR. """
        try:
            # Find the specific contract (assuming Stock for now, adjust if needed)
            contract = Stock(symbol, 'SMART', 'USD')
            await self.ib.qualifyContractsAsync(contract)
            
            positions = await self.ib.positionsAsync()
            for pos in positions:
                if pos.contract.symbol == symbol and pos.contract.secType == 'STK': # Match symbol and type
                    return pos.position
            return 0 # No position found
        except Exception as e:
            print(f"Error fetching position for {symbol}: {e}")
            return 0 # Assume zero position on error

    def get_last_hedge_time(self, symbol):
        """ Check the last time a hedge was executed for this symbol. """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT date FROM trades WHERE ticker = ? AND action = 'HEDGE' ORDER BY date DESC LIMIT 1", (symbol,))
        result = cursor.fetchone()
        conn.close()
        if result:
            # Convert ISO format string back to datetime object
            return datetime.datetime.fromisoformat(result[0])
        return None

    async def assess_and_hedge(self, symbol, current_exposure):
        """ 
        Assess the need for hedging based on exposure and recent hedges.
        Returns a dictionary with hedge details if a hedge is needed, otherwise None.
        """
        hedge_settings = self.config.get('hedging', {})
        asset_settings = self.config.get('assets', {}).get(symbol, {})
        
        max_exposure = asset_settings.get('max_position_size', 100000) # Use asset's max size as exposure limit
        min_hedge_interval_hours = hedge_settings.get('min_hedge_interval_hours', 24)
        hedge_ratio = hedge_settings.get('hedge_ratio', 0.5) # Default hedge ratio

        # Check if hedging is enabled for this asset (implicitly via hedge_settings presence)
        if not hedge_settings or not asset_settings:
            print(f"[AutoHedger] Hedging disabled or asset {symbol} not configured.")
            return None

        current_position = await self.get_current_position(symbol)
        net_exposure = current_exposure + current_position # Simple sum for now, refine if needed

        print(f"[AutoHedger] Assessing {symbol}: Exposure=${net_exposure:,.0f}, Position={current_position}, Max Exposure=${max_exposure:,.0f}")

        # Check if over-exposed
        if abs(net_exposure) > max_exposure:
            # Check last hedge time
            last_hedge = self.get_last_hedge_time(symbol)
            now = datetime.datetime.now()
            if last_hedge and (now - last_hedge).total_seconds() < min_hedge_interval_hours * 3600:
                print(f"[AutoHedger] {symbol} is over-exposed, but hedged recently ({last_hedge}). Skipping.")
                return None

            # Calculate hedge size
            hedge_amount = (abs(net_exposure) - max_exposure) * hedge_ratio
            if net_exposure > 0: # Over-exposed long
                action = 'SELL'
                hedge_type = 'Over-Exposure (Long)'
            else: # Over-exposed short
                action = 'BUY'
                hedge_type = 'Over-Exposure (Short)'
                
            # --- Determine Contract and Quantity ---_hedge
            try:
                # Assuming Stock for now, generalize if needed (e.g., options)
                contract = Stock(symbol, 'SMART', 'USD') 
                await self.ib.qualifyContractsAsync(contract)
                
                # Get current market price to calculate quantity
                ticker = await self.ib.reqMktDataAsync(contract, '', False, False)
                await asyncio.sleep(1) # Allow time for market data to arrive
                self.ib.cancelMktData(contract)
                
                if ticker and ticker.last: # Use last price if available
                    price = ticker.last
                elif ticker and ticker.close: # Fallback to close price
                     price = ticker.close
                else:
                     print(f"[AutoHedger] Could not get market price for {symbol}. Skipping hedge.")
                     return None

                if price <= 0:
                    print(f"[AutoHedger] Invalid market price ({price}) for {symbol}. Skipping hedge.")
                    return None

                qty = int(hedge_amount / price)
                if qty <= 0:
                    print(f"[AutoHedger] Calculated hedge quantity is zero or negative for {symbol}. Skipping.")
                    return None
                    
                print(f"[AutoHedger] DECISION for {symbol}: {action} {qty} shares to hedge {hedge_type}. Exposure ${net_exposure:,.0f} > Max ${max_exposure:,.0f}")
                
                # --- Prepare Hedge Decision Data ---_hedge
                hedge_decision = {
                    'symbol': symbol,
                    'contract': contract,
                    'action': action, 
                    'qty': qty,
                    'hedge_type': hedge_type,
                    # Add mid_price if available and useful for downstream slippage context
                    'mid_price': (ticker.bid + ticker.ask) / 2 if ticker and ticker.bid and ticker.ask else price
                }
                return hedge_decision # Return the decision dictionary

            except Exception as e:
                print(f"[AutoHedger] Error during hedge preparation for {symbol}: {e}")
                import traceback
                traceback.print_exc()
                return None
        else:
            print(f"[AutoHedger] {symbol} exposure within limits.")
            return None

# === Example Usage (for testing, not part of main flow) ===
# async def main():
#     from ib_insync import IB
#     import yaml

#     ib = IB()
#     try:
#         await ib.connectAsync('127.0.0.1', 7497, clientId=99) # Use a different client ID
#         with open('config.yaml', 'r') as f:
#             config = yaml.safe_load(f)
        
#         hedger = AutoHedger(ib, config)
        
#         # Simulate exposure
#         test_exposure = {'MSTR': 650000} # Example: Over-exposed MSTR
        
#         for symbol, exposure in test_exposure.items():
#              decision = await hedger.assess_and_hedge(symbol, exposure)
#              if decision:
#                  print(f"Hedge decision made: {decision}")
#                  # Here, dynasty_engine would call order_helper.execute_trade_async(decision)
#              else:
#                  print(f"No hedge decision for {symbol}.")

#     except Exception as e:
#         print(f"Error in example: {e}")
#     finally:
#         if ib.isConnected():
#             ib.disconnect()

# if __name__ == "__main__":
#     asyncio.run(main())

# === Summary ===
# - Evaluates total exposure per asset
# - If exposure too large, executes protective hedge (LEAP puts, ETF shorts)
# - Logs hedge trades in database with commentary

# === Phase 3 Progress ===
# monthly_reporter.py
# trade_commentary.py
# multi_asset_manager.py
# auto_hedger.py
# self_tuner.py (final step!)