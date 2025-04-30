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
from options_utils import build_strangle_contracts, build_straddle_contracts, build_option_contract

# === Multi-leg contract builders (scaffold) ===
def build_bull_call_spread(symbol, price, days_out=7, exchange="SMART"):
    """Return (long call, short call) for bull call spread."""
    long_call = build_option_contract(symbol, price, right="C", strike_offset_pct=0.02, days_out=days_out, exchange=exchange)
    short_call = build_option_contract(symbol, price, right="C", strike_offset_pct=0.05, days_out=days_out, exchange=exchange)
    return long_call, short_call

def build_bear_put_spread(symbol, price, days_out=7, exchange="SMART"):
    """Return (long put, short put) for bear put spread."""
    long_put = build_option_contract(symbol, price, right="P", strike_offset_pct=0.05, days_out=days_out, exchange=exchange)
    short_put = build_option_contract(symbol, price, right="P", strike_offset_pct=0.02, days_out=days_out, exchange=exchange)
    return long_put, short_put

def build_covered_call(symbol, price, days_out=7, exchange="SMART"):
    """Return (stock, short call) for covered call."""
    stock = Stock(symbol, exchange, 'USD')
    call = build_option_contract(symbol, price, right="C", strike_offset_pct=0.05, days_out=days_out, exchange=exchange)
    return stock, call
# === End multi-leg contract builders ===
from agent_logger import log_agent_decision
# Get a logger for this module
logger = logging.getLogger(__name__)

class AssetWatcher:
    def __init__(self, ibkr_connection, config):
        self.ib = ibkr_connection
        self.config = config['assets']

    async def fetch_asset_data(self, symbol):
        # Fetch market data (live only)
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                stock = Stock(symbol, 'SMART', 'USD')
                market_data = self.ib.reqMktData(stock)
                await asyncio.sleep(5)
                if market_data.last and not math.isnan(market_data.last):
                    return market_data.last
                else:
                    logger.warning(f"[AssetWatcher] No valid market_data.last for {symbol}. Skipping asset.")
                    return None
            except Exception as e:
                logger.error(f"[AssetWatcher] Error fetching data for {symbol} (attempt {attempt+1}): {e}")
                time.sleep(2 ** attempt)
        return None

class AssetAllocator:
    def __init__(self, ib_instance, config):
        self.ib = ib_instance
        self.asset_config = config['assets']
        # --- In-memory position and stop-loss tracking ---
        # Structure: {symbol: { 'entry_price': float, 'qty': int, 'stop_loss': float, 'side': str, 'timestamp': float }}
        self.positions = {}
        self.stop_loss_pct = 0.05  # 5% stop-loss by default (can be made per-asset)

    # Make the function asynchronous
    async def evaluate_and_trade(self, symbol, rl_action=None):
        asset_settings = self.asset_config.get(symbol)
        if not asset_settings:
            logger.info(f"[Dynasty Multi-Asset] No config found for {symbol}")
            return None

        # --- RL Action Mapping ---
        # Map RL action codes to strategy logic. rl_action should be an int from the RL agent.
        # 0: HOLD
        # 1: BUY stock (long)
        # 2: SELL stock (flat/short)
        # 3: ENTER bull call spread
        # 4: EXIT bull call spread
        # 5: ENTER bear put spread
        # 6: EXIT bear put spread
        # 7: ENTER covered call
        # 8: EXIT covered call
        # 9: ENTER crypto futures long
        # 10: EXIT crypto futures long
        # 11: ENTER stop-loss
        # 12: ENTER take-profit

        # Example RL action dispatcher (expand as needed)
        from dyn_engine.execution import get_execution_service
        from dyn_engine.risk_manager import get_risk_manager
        exec_service = get_execution_service(self.ib)
        risk_manager = get_risk_manager()
        # --- Reward shaping & trade filter scaffold ---
        # reward = 1 if monthly P&L > 5%, else penalize (to be implemented in RL env)
        # Only execute trades that pass risk filter and expected profit filter

        try:
            # --- Stop-loss check for open position ---
            # Only for single-stock for now (extend to spreads/covered calls if needed)
            price = None
            asset_settings = self.asset_config.get(symbol)
            contract = Stock(asset_settings.get('ibkr_symbol', symbol), 'SMART', 'USD')
            try:
                mkt_data = self.ib.reqMktData(contract, '', False, False)
                await asyncio.sleep(2)
                if mkt_data and (mkt_data.last or (mkt_data.bid and mkt_data.ask)):
                    price = mkt_data.last if mkt_data.last and not math.isnan(mkt_data.last) else (mkt_data.bid + mkt_data.ask) / 2.0
                self.ib.cancelMktData(contract)
            except Exception as e:
                logger.error(f"[Stop-Loss] Error fetching price for {symbol}: {e}")

            pos = self.positions.get(symbol)
            stop_loss_triggered = False
            if pos and price:
                if pos['side'] == 'long' and price <= pos['stop_loss']:
                    logger.warning(f"[Stop-Loss] Triggered for {symbol}: price={price:.2f} stop_loss={pos['stop_loss']:.2f}")
                    # Execute SELL to close
                    result = await exec_service.execute_trade(contract, 'SELL', pos['qty'])
                    logger.info(f"[Stop-Loss] Executed forced SELL: {result}")
                    # Log event for dashboard analytics
                    with open('data/stop_loss_events.csv', 'a') as f:
                        f.write(f"{symbol},SELL,{pos['qty']},{pos['entry_price']},{price},{pos['stop_loss']},STOP_LOSS,{result.status}\n")
                    del self.positions[symbol]
                    # Dump open positions for API
                    try:
                        import json
                        with open('data/open_positions.json', 'w') as pf:
                            json.dump(list(self.positions.values()), pf)
                    except Exception as dump_exc:
                        logger.error(f"[Stop-Loss] Error dumping open positions: {dump_exc}")
                    stop_loss_triggered = True
                elif pos['side'] == 'short' and price >= pos['stop_loss']:
                    logger.warning(f"[Stop-Loss] Triggered for {symbol} (short): price={price:.2f} stop_loss={pos['stop_loss']:.2f}")
                    result = await exec_service.execute_trade(contract, 'BUY', pos['qty'])
                    logger.info(f"[Stop-Loss] Executed forced BUY: {result}")
                    with open('data/stop_loss_events.csv', 'a') as f:
                        f.write(f"{symbol},BUY,{pos['qty']},{pos['entry_price']},{price},{pos['stop_loss']},STOP_LOSS,{result.status}\n")
                    del self.positions[symbol]
                    try:
                        import json
                        with open('data/open_positions.json', 'w') as pf:
                            json.dump(list(self.positions.values()), pf)
                    except Exception as dump_exc:
                        logger.error(f"[Stop-Loss] Error dumping open positions: {dump_exc}")
                    stop_loss_triggered = True
            if stop_loss_triggered:
                return None

            if rl_action == 0:
                logger.info(f"RL: HOLD for {symbol}")
                return None
            elif rl_action == 1:
                logger.info(f"RL: BUY stock for {symbol}")
                qty = asset_settings.get('qty', 1)
                result = await exec_service.execute_trade(contract, 'BUY', qty)
                logger.info(f"Executed BUY stock: {result}")
                # Track position for stop-loss
                if price:
                    stop_loss = price * (1 - self.stop_loss_pct)
                    self.positions[symbol] = {'symbol': symbol, 'entry_price': price, 'qty': qty, 'stop_loss': stop_loss, 'side': 'long'}
                    # Dump open positions for API
                    try:
                        import json
                        with open('data/open_positions.json', 'w') as pf:
                            json.dump(list(self.positions.values()), pf)
                    except Exception as dump_exc:
                        logger.error(f"[Trade] Error dumping open positions: {dump_exc}")
                return result
            elif rl_action == 2:
                logger.info(f"RL: SELL stock for {symbol}")
                qty = asset_settings.get('qty', 1)
                result = await exec_service.execute_trade(contract, 'SELL', qty)
                logger.info(f"Executed SELL stock: {result}")
                # Remove position if exists
                if symbol in self.positions:
                    del self.positions[symbol]
                    # Dump open positions for API
                    try:
                        import json
                        with open('data/open_positions.json', 'w') as pf:
                            json.dump(list(self.positions.values()), pf)
                    except Exception as dump_exc:
                        logger.error(f"[Trade] Error dumping open positions: {dump_exc}")
                return result
            elif rl_action == 3:
                logger.info(f"RL: ENTER bull call spread for {symbol}")
                long_call, short_call = build_bull_call_spread(symbol, asset_settings.get("price_hint", 0) or 100)
                # Risk check: skip if not allowed
                # if not risk_manager.check_entry(symbol, 'bull_call_spread', 'ENTER'): return None
                results = await exec_service.execute_multi_leg_trade([long_call, short_call], ['BUY', 'SELL'], [1, 1])
                logger.info(f"Executed bull call spread: {results}")
                return results
            elif rl_action == 4:
                logger.info(f"RL: EXIT bull call spread for {symbol}")
                # Placeholder: unwind logic (would need to track open positions)
                return None
            elif rl_action == 5:
                logger.info(f"RL: ENTER bear put spread for {symbol}")
                long_put, short_put = build_bear_put_spread(symbol, asset_settings.get("price_hint", 0) or 100)
                # if not risk_manager.check_entry(symbol, 'bear_put_spread', 'ENTER'): return None
                results = await exec_service.execute_multi_leg_trade([long_put, short_put], ['BUY', 'SELL'], [1, 1])
                logger.info(f"Executed bear put spread: {results}")
                return results
            elif rl_action == 6:
                logger.info(f"RL: EXIT bear put spread for {symbol}")
                # Placeholder: unwind logic
                return None
            elif rl_action == 7:
                logger.info(f"RL: ENTER covered call for {symbol}")
                stock, call = build_covered_call(symbol, asset_settings.get("price_hint", 0) or 100)
                results = await exec_service.execute_multi_leg_trade([stock, call], ['BUY', 'SELL'], [asset_settings.get('qty', 1), 1])
                logger.info(f"Executed covered call: {results}")
                return results
            elif rl_action == 8:
                logger.info(f"RL: EXIT covered call for {symbol}")
                # Placeholder: unwind logic
                return None
            elif rl_action == 9:
                logger.info(f"RL: ENTER crypto futures long for {symbol}")
                contract = Stock(symbol, 'SMART', 'USD')  # Placeholder for future
                result = await exec_service.execute_trade(contract, 'BUY', asset_settings.get('qty', 1))
                logger.info(f"Executed crypto futures long: {result}")
                return result
            elif rl_action == 10:
                logger.info(f"RL: EXIT crypto futures long for {symbol}")
                contract = Stock(symbol, 'SMART', 'USD')
                result = await exec_service.execute_trade(contract, 'SELL', asset_settings.get('qty', 1))
                logger.info(f"Executed crypto futures exit: {result}")
                return result
            elif rl_action == 11:
                logger.info(f"RL: ENTER stop-loss for {symbol}")
                # Placeholder: trigger stop-loss logic (to be implemented)
                return None
            elif rl_action == 12:
                logger.info(f"RL: ENTER take-profit for {symbol}")
                # Placeholder: trigger take-profit logic (to be implemented)
                return None
            else:
                logger.warning(f"RL: Unknown action {rl_action} for {symbol}")
                return None
        except Exception as e:
            logger.error(f"RL: Exception in evaluate_and_trade for {symbol}: {e}")
            return None

        # --- Existing contract/instrument logic (fallback for non-RL mode) ---
        instrument = asset_settings.get("instrument", "stock")
        # ... (existing instrument logic remains unchanged) ...

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
        # Optionally, set defaults for expected_mu and expected_sigma if needed
        # expected_mu = asset_settings.get('expected_mu', 0.10) # Example: 10% expected annual return
        # expected_sigma = asset_settings.get('expected_sigma', 0.20) # Example: 20% annual volatility
        # --- End Placeholder ---

        # Build RL observation vector (example: price, iv_rank or vol) – extend as needed
        import numpy as np
        from rl_policy import decide as rl_decide
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

        # Kelly sizing – simplistic position sizing (per contract / shares)
        kelly_f = kelly_fraction(expected_mu, expected_sigma)
        qty = max(1, int(kelly_f * 10))  # TODO scale properly

        # Generate trade commentary and log decision for Streamlit
        try:
            from trade_commentary import generate_trade_commentary
            commentary = generate_trade_commentary(symbol, rl_action, qty, price, iv_rank, None)
        except Exception as e:
            commentary = f"Commentary error: {e}"
        try:
            log_agent_decision(symbol, obs_vec, rl_action, commentary)
        except Exception as e:
            logger.error(f"[AgentLogger] Failed to log agent decision: {e}")

        if rl_action == 0:
            logger.debug("[Dynasty] Hold action – no trades executed.")
            return None

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
                # Log trade decision
                try:
                    log_agent_decision(symbol, obs_vec, rl_action, commentary, error=None)
                except Exception as e:
                    logger.error(f"[AgentLogger] Failed to log agent decision: {e}")

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