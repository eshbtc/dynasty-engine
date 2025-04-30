# Dynasty Engine MVP Bot - DynastyEngine.py v2 (with Memory Enhancer + Live PnL Dashboard + Mobile Access)

# Core Imports
import asyncio
import datetime
from ib_insync import *
import yaml
import sqlite3
import os
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import openai
import requests
import pandas as pd
import streamlit as st
import random
from prometheus_client import Gauge
import math
from agentic_core import decide, reflect
from dyn_engine.async_db import get_db  # new async DB
from dyn_engine.metrics import observe_latency, eval_assets_latency, eval_hedges_latency, start_health_server, record_error
from settings import get_settings
from dyn_engine.logging_config import get_logger
from dyn_engine import metrics as MET

# Structured logger via structlog
logger = get_logger(__name__)
cfg = get_settings()

# GCP Secrets Fetcher
def get_secret(secret_id):
    return os.environ.get(secret_id)

# Load Configs
def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Setup IBKR
IBKR_USERNAME = get_secret('IBKR_USERNAME')
IBKR_PASSWORD = get_secret('IBKR_PASSWORD')
ib: IB | None = None  # Will be injected by engine_app
IBKR_HOST = '127.0.0.1'
IBKR_PORT = 7497
IBKR_CLIENT_ID = 1
DB_PATH = 'trade_tracker.db'

# Setter for dependency injection from EngineApp
def set_ib(ib_instance: IB):
    global ib
    ib = ib_instance

# Start health endpoint
start_health_server(cfg.prom_port + 1)

# --- DB Migration Check: Add slippage_bp column if missing ---
logger.info("Checking database schema...")
try:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(trades)")
    cols = [c[1] for c in cur.fetchall()]
    if 'slippage_bp' not in cols:
        logger.info("Adding 'slippage_bp' column to 'trades' table...")
        cur.execute("ALTER TABLE trades ADD COLUMN slippage_bp REAL")
        conn.commit()
        logger.info("'slippage_bp' column added.")
    else:
        logger.info("'slippage_bp' column already exists.")
except sqlite3.Error as e:
    logger.error(f"Database error during migration check: {e}")
finally:
    if conn:
        conn.close()
logger.info("Database schema check complete.")
# --------------------------------------------------------------

# Prometheus Metrics for Drawdown
MET.init_metrics(cfg.prom_port)
drawdown_gauge = MET.drawdown_gauge
health_gauge = MET.health_gauge
manual_halt_flag = False # Global flag for manual halt
max_equity_so_far = 0.0 # Track max equity for drawdown
logger.info("Prometheus metrics server started on port %d", cfg.prom_port)

# Notification Function
def notify(message):
    webhook_url = cfg.slack_webhook_url or (config.get('slack_webhook_url') if isinstance(config, dict) else None)
    if webhook_url:
        try:
            requests.post(webhook_url, json={"text": message}, timeout=5)
        except Exception as e:
            logger.warning("Failed to send Slack notification: %s", e)
    else:
        logger.debug("Slack webhook not configured; message: %s", message)

# Core Bot Logic
async def dynasty_engine_cycle():
    """Main trading logic cycle."""
    logger.info("Running Dynasty Engine Cycle...")
    health_gauge.set(1) # Assume healthy at start of cycle

    # --- Risk Halt Check --- START ---
    try:
        # TODO: replace placeholder with actual IB call
        current_equity = 1_000_000.0  # placeholder

        from dyn_engine.risk_manager import get_risk_manager
        rm = get_risk_manager()
        should_halt, dd_pct = rm.update_and_check(current_equity)
        drawdown_gauge.set(round(dd_pct, 2))

        if should_halt:
            halt_reason = (
                f"Drawdown {dd_pct:.2f}% > 5%" if dd_pct > 0 else "Manual DYNASTY_HALT flag set"
            )
            logger.info("[HALT] %s – skipping new trades this cycle.", halt_reason)
            health_gauge.set(0)
            return

    except Exception as e:
        logger.error("[Error] RiskManager check failed: %s", e)
        health_gauge.set(0)
        return

    await adapt_from_memory()

    global config
    config = load_config()
    if config is None: # Handle case where config loading fails
        logger.error("[Error] Failed to load config. Halting cycle.")
        health_gauge.set(0)
        return

    # Ensure IB connection injected
    if ib is None or not ib.isConnected():
        logger.error("IB instance not connected – cycle skipped.")
        health_gauge.set(0)
        return

    stock = Stock('MSTR', 'SMART', 'USD')
    await ib.qualifyContractsAsync(stock)
    market_data = ib.reqMktData(stock, '', False, False)
    await asyncio.sleep(2) # Shorter sleep after reqMktData

    if not market_data or market_data.last is None or math.isnan(market_data.last):
         logger.error(f"[Error] Failed to get valid market data for {stock.symbol}. Halting cycle.")
         ib.cancelMktData(stock)
         health_gauge.set(0)
         return

    price = market_data.last
    ib.cancelMktData(stock) # Cancel subscription after getting data

    # TODO: Replace dummy IV with real data (e.g., from iv_data.py)
    iv_rank = 25  # Dummy value - REPLACE

    # Features to agent
    features = {
        "ticker": stock.symbol,
        "price": price,
        "iv_rank": iv_rank,
        "btc_correlation": 0.8, # Example - Fetch real correlation if needed
        "current_position": 0 # Example - Fetch real position size
    }

    # --- New Agentic Core Logic --- START ---
    logger.info(f"Querying agent with features: {features}")
    resp = decide(features)
    agent_content = resp.get('content')
    function_call = resp.get('function_call')

    if function_call and function_call['name'] == 'place_trade':
        try:
            payload = json.loads(function_call['arguments'])
            action = payload.get('action')
            size = payload.get('size', 0)
            ticker = payload.get('ticker') # Agent confirms ticker

            # Validate ticker from agent against the one we queried features for
            if ticker != stock.symbol:
                logger.warning(f"Warning: Agent requested trade for {ticker}, but features were for {stock.symbol}. Ignoring trade.")
                notify(f"Agent Warning: Mismatched ticker {ticker} vs {stock.symbol}")
            elif action in ['BUY', 'SELL'] and size > 0:
                logger.info(f"Agent decided: {action} {size} {ticker}")
                from dyn_engine.execution import get_execution_service
                exec_service = get_execution_service(ib)
                # Use positive qty; action distinguishes side
                result = await exec_service.execute_trade(stock, action, size)

                if result.status.upper() in ("FILLED", "CLOSED", "SUBMITTED"):
                    logger.info(
                        "Executed %s %s %s at %.2f (slippage %.2fbp, fee %.2f)",
                        action,
                        size,
                        ticker,
                        result.avg_fill_price,
                        result.slippage_bp,
                        result.commission,
                    )
                    notify(
                        f"Executed {action} {size} {ticker} at ~{result.avg_fill_price:.2f}. Fee: ${result.commission:.2f}"
                    )
                    try:
                        db = await get_db()
                        trade_result = {
                            'ticker': ticker,
                            'action': action,
                            'quantity': size,
                            'price': result.avg_fill_price,
                            'date': datetime.datetime.now().isoformat(),
                            'outcome': result.status.upper(),
                            'fee': result.commission,
                            'slippage_bp': result.slippage_bp,
                        }
                        await db.save_trade(trade_result)
                    except Exception as e:
                        logger.warning("Failed to log trade result: %s", e)
                else:
                    logger.warning("Trade execution failed or pending: %s", result.status)
                    notify(f"Trade {action} {ticker} status {result.status}")
            elif action == 'HOLD':
                logger.info(f"Agent decided: HOLD {ticker}")
                notify(f"Agent HOLD {ticker}")
            else:
                # Invalid action/size combination from agent
                logger.error(f"Invalid action/size from agent: {action} {size} for {ticker}")
                notify(f"Agent Warning: Invalid action/size {action}/{size} for {ticker}")

        except json.JSONDecodeError:
            logger.error("[Error] Could not decode agent function call arguments.")
            notify("Agent Error: Invalid trade arguments.")
        except Exception as e:
            # Catch potential errors during order placement or reflection
            logger.error(f"[Error] Processing agent trade execution failed: {e}")
            notify(f"Agent Execution Error: {e}")
            health_gauge.set(0) # Mark as unhealthy if agent execution fails

    elif agent_content:
        # Agent provided a text response instead of a function call
        logger.info(f"Agent Response: {agent_content}")
        notify(f"Agent says: {agent_content}")
    else:
        # No function call and no content, unusual state
        logger.warning("[Warning] Agent returned no function call or content.")
        notify("Agent Warning: No decision returned.")
    # --- New Agentic Core Logic --- END ---

    logger.info("Dynasty Engine Cycle Complete.")

# Schedule Bot
scheduler = AsyncIOScheduler()
scheduler.add_job(dynasty_engine_cycle, 'interval', minutes=30)
# Scheduler start is controlled by dyn_engine.engine_app

# Run Bot Forever
# Event loop run is handled by dyn_engine.engine_app

# === dynasty_engine.py update for Multi-Asset ===

from multi_asset_manager import AssetAllocator
from auto_hedger import AutoHedger

@observe_latency(eval_assets_latency)
async def evaluate_assets():
    try:
        # Reload config each call
        global config
        config = load_config()
        if ib is None or not ib.isConnected():
            logger.warning("IB not connected in evaluate_assets; skipping.")
            return
        asset_allocator = AssetAllocator(ib, config)
        from dyn_engine.execution import get_execution_service
        exec_service = get_execution_service(ib)
        db = await get_db()
        for asset in config.get('assets', {}).keys():
            trade_decision = await asset_allocator.evaluate_and_trade(asset)
            if not trade_decision:
                continue
            result = await exec_service.execute_trade(
                trade_decision['contract'],
                trade_decision['action'],
                trade_decision['qty'],
            )
            if result.status.upper() in ("FILLED", "CLOSED", "SUBMITTED"):
                record = {
                    'ticker': asset,
                    'action': trade_decision['action'],
                    'quantity': trade_decision['qty'],
                    'price': result.avg_fill_price,
                    'date': datetime.datetime.now().isoformat(),
                    'outcome': result.status.upper(),
                    'fee': result.commission,
                    'slippage_bp': result.slippage_bp,
                    'strategy': trade_decision.get('strategy'),
                }
                await db.save_trade(record)
                logger.info("Asset trade saved for %s", asset)
                MET.record_trade(kind="asset", status=result.status, commission=result.commission, slippage_bp=result.slippage_bp)

        # Hedging phase using AutoHedger
        hedger = AutoHedger(ib, config)
        # Placeholder exposure – should calculate from portfolio
        exposure_map = {'MSTR': 600000, 'BTC': 280000, 'ETH': 140000}
        for symbol, exposure in exposure_map.items():
            hedge_decision = await hedger.assess_and_hedge(symbol, exposure)
            if hedge_decision:
                result = await exec_service.execute_trade(
                    hedge_decision['contract'],
                    hedge_decision['action'],
                    hedge_decision['qty'],
                )
                if result.status.upper() in ("FILLED", "CLOSED", "SUBMITTED"):
                    record = {
                        'ticker': symbol,
                        'action': 'HEDGE',
                        'quantity': hedge_decision['qty'],
                        'price': result.avg_fill_price,
                        'date': datetime.datetime.now().isoformat(),
                        'outcome': result.status.upper(),
                        'fee': result.commission,
                        'slippage_bp': result.slippage_bp,
                    }
                    await db.save_trade(record)
                    logger.info("Hedge trade saved for %s", symbol)
                    MET.record_trade(kind="hedge", status=result.status, commission=result.commission, slippage_bp=result.slippage_bp)
    except Exception as exc:
        record_error("evaluate_assets")
        logger.error("evaluate_assets error: %s", exc)

@observe_latency(eval_hedges_latency)
async def evaluate_hedges():
    try:
        global config # Use latest config
        logger.info("--- Evaluating Hedges ---")
        db = await get_db()
        conn = db.conn

        # --- TODO: Calculate Current Exposure Dynamically ---_hedges
        # This needs a robust way to calculate total portfolio exposure per asset.
        # For now, using placeholder values. Replace with actual portfolio query/calculation.
        # Example: Query IBKR portfolio, sum positions across related underlyings.
        current_exposure_placeholders = {
            'MSTR': 600000,
            'BTC': 280000, # Placeholder - need actual calculation
            'ETH': 140000  # Placeholder - need actual calculation
        }
        logger.info(f"[evaluate_hedges] Using placeholder exposure values: {current_exposure_placeholders}")
        # --- End Placeholder ---

        from dyn_engine.execution import get_execution_service
        exec_service = get_execution_service(ib)
        for symbol, exposure in current_exposure_placeholders.items():
            # Only assess assets present in the main config (avoids hedging unmanaged assets)
            if symbol in config.get('assets', {}):
                logger.info(f"Assessing hedge need for: {symbol} with exposure {exposure}")
                try:
                    from auto_hedger import AutoHedger
                    hedger = AutoHedger(ib, config)
                    hedge_decision = await hedger.assess_and_hedge(symbol, exposure)

                    if hedge_decision:
                        logger.info(f"Hedge Decision for {symbol}: {hedge_decision['action']} {hedge_decision['qty']} ({hedge_decision['hedge_type']})")
                        # --- Execute Hedge ---_hedges
                        result = await exec_service.execute_trade(
                            contract=hedge_decision['contract'],
                            action=hedge_decision['action'],
                            quantity=hedge_decision['qty'],
                        )

                        # --- Process Execution Result ---_hedges
                        if result.status.upper() in ("FILLED", "CLOSED", "SUBMITTED"):
                            logger.info("Hedge Execution Success for %s: %s", symbol, result.status)
                            # Generate commentary for hedge
                            commentary = f"Auto hedge ({hedge_decision['hedge_type']}) executed due to exposure limit breach."
                            
                            # Save to database using ACTUAL execution data
                            hedge_result = {
                                'ticker': symbol,
                                'action': 'HEDGE',
                                'quantity': hedge_decision['qty'],
                                'price': result.avg_fill_price,
                                'date': datetime.datetime.now().isoformat(),
                                'outcome': result.status.upper(),
                                'fee': result.commission,
                                'slippage_bp': result.slippage_bp,
                            }
                            await db.save_trade(hedge_result) # Save hedge result to DB
                            logger.info("Hedge trade for {symbol} saved to database (async).")
                            MET.record_trade(kind="hedge", status=result.status, commission=result.commission, slippage_bp=result.slippage_bp)
                        else:
                            logger.error(f"Hedge Execution FAILED or Pending for {symbol}: Status {result.get('status', 'Unknown')}")
                except Exception as e:
                    logger.error(f"ERROR evaluating/executing hedge for {symbol}: {e}")
                    import traceback
                    traceback.print_exc()
    except Exception as exc:
        record_error("evaluate_hedges")
        logger.error("evaluate_hedges error: %s", exc)