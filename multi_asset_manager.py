# Dynasty Engine Phase 3 - Multi-Asset Manager Module (multi_asset_manager.py)

import asyncio
import logging
from ib_insync import *
from asset_watcher import AssetWatcher
from iv_data import iv_rank_polygon, crypto_realized_vol
from kelly import kelly_fraction # Import the Kelly function
import math
from feature_builder import build_obs
from dyn_engine.risk_manager import get_risk_manager
from episode_logger import log_step
from metrics_exporter import ensure_exporter, update_action, update_equity, record_rl_latency
# Options helpers
from options_utils import build_strangle_contracts, build_straddle_contracts
# Get a logger for this module
logger = logging.getLogger(__name__)

class AssetWatcher:
    def __init__(self, ibkr_connection, config):
        self.ib = ibkr_connection
        self.config = config['assets']

    async def fetch_asset_data(self, symbol):
        # Fetch market data (live only)
        stock = Stock(symbol, 'SMART', 'USD')
        market_data = self.ib.reqMktData(stock)
        await asyncio.sleep(5)
        if market_data.last and not math.isnan(market_data.last):
            return market_data.last
        else:
            logger.warning(f"[AssetWatcher] No valid market_data.last for {symbol}. Skipping asset.")
            return None

class AssetAllocator:
    def __init__(self, ib_instance, config):
        self.ib = ib_instance
        self.asset_config = config['assets']

    # Make the function asynchronous
    async def evaluate_and_trade(self, symbol):
        asset_settings = self.asset_config.get(symbol)
        if not asset_settings:
            logger.info(f"[Dynasty Multi-Asset] No config found for {symbol}")
            return None

        # --- Define Contract / Instruments ---
        instrument = asset_settings.get("instrument", "stock")

        if symbol in ('BTC', 'ETH'): # Placeholder for Crypto Futures/Proxies if needed
             # Example: contract = Future('BRR', '202412', 'CME')
             logger.info(f"[Dynasty Multi-Asset] Crypto {symbol} - Trading logic not fully implemented for specific contracts.")
             # contract = Stock(symbol, 'SMART', 'USD') # Fallback for simulation if needed
             contract = Stock(asset_settings.get('ibkr_symbol', symbol), 'SMART', 'USD', primaryExchange=asset_settings.get('primary_exchange', '')) # Use config for symbol/exchange
        elif instrument == "strangle":
            # we create placeholder stock contract for price feed first; option contracts later
            contract = Stock(asset_settings.get('ibkr_symbol', symbol), 'SMART', 'USD', primaryExchange=asset_settings.get('primary_exchange', ''))
        else:
            contract = Stock(asset_settings.get('ibkr_symbol', symbol), 'SMART', 'USD', primaryExchange=asset_settings.get('primary_exchange', ''))

        # --- Fetch Real Market Data ---_trade
        try:
            # Ensure IB connection is active
            if not self.ib.isConnected():
                logger.info("[Dynasty Multi-Asset] IBKR not connected. Attempting to reconnect...")
                await self.ib.connectAsync('127.0.0.1', 7497, clientId=1) # Adjust host/port/clientId as needed
            
            # Request market data
            mkt_data = self.ib.reqMktData(contract, '', False, False)
            await asyncio.sleep(2) # Allow time for data to arrive
            
            if mkt_data and (mkt_data.last or (mkt_data.bid and mkt_data.ask)):
                price = mkt_data.last if mkt_data.last and not math.isnan(mkt_data.last) else (mkt_data.bid + mkt_data.ask) / 2.0
                mid_price = (mkt_data.bid + mkt_data.ask) / 2.0 if mkt_data.bid and mkt_data.ask else price # Use mid if available
            else:
                logger.warning(f"[Dynasty Multi-Asset] Failed to get market data for {symbol}. Ticker: {mkt_data}")
                # Attempt tickByTick data as a fallback
                # ticks = self.ib.reqTickByTickData(contract, 'Last', 1, False)
                # await asyncio.sleep(1)
                # if ticks:
                #     price = ticks[0].price
                # else:
                #     logger.warning(f"[Dynasty Multi-Asset] Tick-by-tick data failed for {symbol}.")
                #     return None # Exit if no price data
                price = None # Set price to None if data is invalid
            
            self.ib.cancelMktData(contract) # Cancel subscription after getting data
            
            if price is None or price <= 0:
                logger.warning(f"[Dynasty Multi-Asset] Could not get valid price for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"[Dynasty Multi-Asset] Error fetching market data for {symbol}: {e}")
            self.ib.cancelMktData(contract) # Ensure cancellation on error
            return None
        # --- End Market Data Fetch ---

        # --- Fetch IV / Volatility --- (Keep using existing data_provider)
        # TODO: Consider making data_provider async if network calls become blocking
        iv_rank = None
        volatility = None
        try:
            if symbol in ('BTC', 'ETH'):
                volatility = crypto_realized_vol(symbol)
            else:
                iv_rank = iv_rank_polygon(symbol)
        except Exception as e:
            logger.error(f"[Dynasty Multi-Asset] Error fetching IV/Volatility for {symbol}: {e}")
        # --- End IV / Volatility Fetch ---

        strategy = asset_settings.get('strategy', 'hold')
        logger.info(f"[Dynasty Multi-Asset] Evaluating {symbol} ({contract.symbol}) with strategy {strategy} at price {price:.2f} (Mid: {mid_price:.2f})")

        # --- Calculate/Fetch Expected Mu and Sigma ---
        expected_mu = asset_settings.get('expected_mu', None)
        sigma = asset_settings.get('sigma', None)
        if expected_mu is None or sigma is None or expected_mu == 'PLACEHOLDER' or sigma == 'PLACEHOLDER':
            logger.warning(f"[Dynasty Multi-Asset] Missing or placeholder expected_mu/sigma for {symbol}. Skipping Kelly sizing and trade.")
            return None
0) # Example: 10% expected annual return
        expected_sigma = asset_settings.get('expected_sigma', 0.20) # Example: 20% annual volatility
        # --- End Placeholder ---

        # Build RL observation vector (example: price, iv_rank or vol) – extend as needed
        import numpy as np
        from rl_policy import decide as rl_decide
        obs_vec = np.array([
            # replaced by feature_builder for consistency
        ], dtype=np.float32)

        obs_vec = build_obs(symbol, price, iv_rank=iv_rank, volatility=volatility)

        # Check risk manager status
        ensure_exporter()
        rm = get_risk_manager()
        nav_val = self.engine_state.nav if hasattr(self, 'engine_state') else 0
        should_halt, dd = rm.update_and_check(nav_val)
        update_equity(nav_val)
        if should_halt:
            logger.warning("[Risk] Trading halted due to drawdown %.2f%%", dd)
            return None

        # Measure RL inference latency
        import time
        ts0 = time.time()
        rl_action = rl_decide(symbol, obs_vec)
        latency_ms = (time.time() - ts0) * 1000
        record_rl_latency(symbol, latency_ms)

        update_action(symbol, rl_action)

        if rl_action == 0:
            logger.debug("[Dynasty] Hold action – no trades executed.")
            return None

        # Action space:
        # 0 HOLD
        # 1 BUY stock  (long delta)
        # 2 SELL stock (short delta)
        # 3 ENTER short strangle (SELL both call+put)
        # 4 EXIT  short strangle (BUY to close)
        # 5 ENTER long  straddle  (BUY both call+put)
        # 6 EXIT  long  straddle  (SELL to close)

        # Kelly sizing – simplistic position sizing (per contract / shares)
        kelly_f = kelly_fraction(expected_mu, expected_sigma)
        qty = max(1, int(kelly_f * 10))  # TODO scale properly

        logger.info("[Dynasty] RL decided action %d, Kelly fraction %.3f -> qty %d", rl_action, kelly_f, qty)

        ensure_exporter()

        try:
            greek_blocked = False

            if rl_action in (1, 2):
                # Stock path
                order_side = "BUY" if rl_action == 1 else "SELL"
                delta_change = qty if rl_action == 1 else -qty
                # Greek exposure check
                if rm.add_greek_exposure(delta_change=delta_change * price, vega_change=0.0):
                    greek_blocked = True
                if not greek_blocked:
                    order = MarketOrder(order_side, qty)
                    trade = self.ib.placeOrder(contract, order)
                    logger.info("[Dynasty] Placed order %s", trade)

            elif rl_action in (3, 4):
                # Strangle path
                call_opt, put_opt = build_strangle_contracts(
                    symbol,
                    mid_price,
                    strike_offset_pct=asset_settings.get("strike_offset_pct", 0.05),
                    days_out=asset_settings.get("days_out", 7),
                )

                enter = rl_action == 3
                call_side = "SELL" if enter else "BUY"
                put_side = "SELL" if enter else "BUY"

                # Approx greeks for risk tracking
                days_out = asset_settings.get("days_out", 7)
                T = days_out / 365.0
                sigma = (iv_rank or 50) / 100.0  # rudimentary fallback

                call_delta = opt_delta(price, call_opt.strike, T, 0.0, sigma)
                put_delta = opt_delta(price, put_opt.strike, T, 0.0, sigma, right="P")
                call_vega = opt_vega(price, call_opt.strike, T, 0.0, sigma)
                put_vega = opt_vega(price, put_opt.strike, T, 0.0, sigma)

                # contract multiplier 100
                multiplier = 100
                net_delta = (call_delta + put_delta) * multiplier * qty
                net_vega = (call_vega + put_vega) * multiplier * qty
                # sign flip for side
                if enter:
                    net_delta *= -1
                    net_vega *= -1

                if rm.add_greek_exposure(delta_change=net_delta, vega_change=net_vega):
                    greek_blocked = True

                if not greek_blocked:
                    call_order = MarketOrder(call_side, qty)
                    put_order = MarketOrder(put_side, qty)
                    call_trade = self.ib.placeOrder(call_opt, call_order)
                    put_trade = self.ib.placeOrder(put_opt, put_order)
                    logger.info("[Dynasty] Strangle trades placed: %s | %s", call_trade, put_trade)

            elif rl_action in (5, 6):
                # Long straddle path
                call_opt, put_opt = build_straddle_contracts(
                    symbol,
                    mid_price,
                    days_out=asset_settings.get("days_out", 7),
                )

                enter = rl_action == 5
                call_side = "BUY" if enter else "SELL"
                put_side = "BUY" if enter else "SELL"

                # Greeks
                days_out = asset_settings.get("days_out", 7)
                T = days_out / 365.0
                sigma = (iv_rank or 50) / 100.0

                call_delta = opt_delta(price, call_opt.strike, T, 0.0, sigma)
                put_delta = opt_delta(price, put_opt.strike, T, 0.0, sigma, right="P")
                call_vega = opt_vega(price, call_opt.strike, T, 0.0, sigma)
                put_vega = opt_vega(price, put_opt.strike, T, 0.0, sigma)

                multiplier = 100
                net_delta = (call_delta + put_delta) * multiplier * qty
                net_vega = (call_vega + put_vega) * multiplier * qty
                # sign for exits
                if not enter:
                    net_delta *= -1
                    net_vega *= -1

                if rm.add_greek_exposure(delta_change=net_delta, vega_change=net_vega):
                    greek_blocked = True

                if not greek_blocked:
                    call_order = MarketOrder(call_side, qty)
                    put_order = MarketOrder(put_side, qty)
                    call_trade = self.ib.placeOrder(call_opt, call_order)
                    put_trade = self.ib.placeOrder(put_opt, put_order)
                    logger.info("[Dynasty] Straddle trades placed: %s | %s", call_trade, put_trade)

            else:
                logger.warning("[Dynasty] RL action %d not recognised", rl_action)

        except Exception as e:
            logger.error("[Dynasty] Order error: %s", e)
            return None

        trade_decision = None # Variable to hold the trade dictionary

        # --- Strategy Evaluation ---_trade
        if strategy == 'leap_puts' and iv_rank is not None and iv_rank < asset_settings.get('entry_iv_rank_threshold', 30):
            kf = kelly_fraction(expected_mu, expected_sigma, r=asset_settings.get('risk_free_rate', 0.0), c=asset_settings.get('max_kelly_constraint', 0.3))
            qty = int(asset_settings['max_position_size'] * kf / price)
            if qty > 0:
                logger.info(f"[Dynasty Multi-Asset] DECISION: Buy {qty} {symbol} (LEAP Puts strategy trigger) at {price:.2f}, IV Rank {iv_rank} (Kelly: {kf:.2f})")
                trade_decision = {'action': 'BUY', 'qty': qty, 'price_target': price, 'mid_price': mid_price, 'strategy': strategy}
                # order = MarketOrder('BUY', qty) # Execution handled by dynasty_engine
                # self.ib.placeOrder(contract, order) # Example: Actual order placement
            else:
                 logger.info(f"[Dynasty Multi-Asset] Kelly fraction resulted in zero quantity for {symbol} (LEAP Puts). No trade.")

        elif strategy == 'swing_volatility' and volatility is not None and volatility > asset_settings.get('entry_volatility_threshold', 50):
            kf = kelly_fraction(expected_mu, expected_sigma, r=asset_settings.get('risk_free_rate', 0.0), c=asset_settings.get('max_kelly_constraint', 0.3))
            qty = int(asset_settings['max_position_size'] * kf / price)
            if qty > 0:
                logger.info(f"[Dynasty Multi-Asset] DECISION: Buy {qty} {symbol} (Swing Volatility trigger) at {price:.2f}, Volatility {volatility} (Kelly: {kf:.2f})")
                trade_decision = {'action': 'BUY', 'qty': qty, 'price_target': price, 'mid_price': mid_price, 'strategy': strategy}
                # order = MarketOrder('BUY', qty)
                # self.ib.placeOrder(contract, order)
            else:
                logger.info(f"[Dynasty Multi-Asset] Kelly fraction resulted in zero quantity for {symbol} (Swing Vol). No trade.")

        elif strategy == 'hedging' and asset_settings.get('trigger_market_downturn', False):
            # Kelly not typically used for fixed hedge legs
            qty = int(asset_settings['max_position_size'] / price) # Use max size for hedge
            if qty > 0:
                 logger.info(f"[Dynasty Multi-Asset] DECISION: Sell {qty} {symbol} (Hedging trigger) at {price:.2f}")
                 trade_decision = {'action': 'SELL', 'qty': qty, 'price_target': price, 'mid_price': mid_price, 'strategy': strategy}
                 # order = MarketOrder('SELL', qty)
                 # self.ib.placeOrder(contract, order)
            else:
                 logger.info(f"[Dynasty Multi-Asset] Zero quantity for hedging {symbol}. No trade.")

        else:
            logger.info(f"[Dynasty Multi-Asset] No action for {symbol} based on current strategy triggers.")

        if trade_decision:
            # Return the contract object along with the decision
            trade_decision['contract'] = contract
            trade_decision['symbol'] = symbol # Add original symbol for clarity
            return trade_decision
        else:
            return None

# === Summary ===
# - Bot scans all assets each Dynasty cycle
# - Chooses action per asset intelligently
# - Fully modular, scalable to more assets later

# === Phase 3 Progress ===
# monthly_reporter.py
# trade_commentary.py
# multi_asset_manager.py
# auto_hedger.py (next!)