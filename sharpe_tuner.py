# ------------------------------------------------------------------
# sharpe_tuner.py  (S‑A)
# ------------------------------------------------------------------
import pandas as pd
import sqlite3
import datetime
import yaml
import numpy as np
import slack_notify as sn
import os # Added for path robustness

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml') # More robust path
DB_PATH = os.path.join(os.path.dirname(__file__), 'trade_tracker.db') # More robust path
WINDOW = 90  # days
STEP = 0.15  # risk sizing step
SLIPPAGE_PENALTY_THRESHOLD_BP = 8 # Slippage threshold in basis points
SLIPPAGE_PENALTY_FACTOR = 0.1 # Reduce size by 10% if threshold breached

def load_cfg():
    try:
        with open(CONFIG_PATH) as f: return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {CONFIG_PATH}")
        return None

def save_cfg(c):
    if c is not None:
        try:
            with open(CONFIG_PATH, 'w') as f: yaml.dump(c, f)
        except IOError as e:
            print(f"Error saving config file: {e}")

def roll_sharpe(series):
    """Calculate annualized Sharpe ratio from a price series."""
    if len(series) < 30: return 0 # Need at least 30 data points for meaningful calculation
    # Calculate daily log returns for better statistical properties
    log_returns = np.log(series[1:] / series[:-1])
    if np.std(log_returns) == 0: return 0 # Avoid division by zero if returns are constant
    # Annualized Sharpe Ratio (assuming 252 trading days)
    sr = np.mean(log_returns) / np.std(log_returns) * np.sqrt(252)
    return round(sr, 2)

def tune():
    """Tunes asset position sizes based on rolling Sharpe ratio."""
    cfg = load_cfg()
    if cfg is None: return

    try:
        conn = sqlite3.connect(DB_PATH)
        # Select necessary columns only, including slippage_bp
        df = pd.read_sql('SELECT date, ticker, price, slippage_bp FROM trades WHERE price > 0', conn)
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return
    except Exception as e: # Catch other potential read errors
        print(f"Error reading trades database: {e}")
        return

    if df.empty:
        print("No trades data found for tuning.")
        return

    df['date'] = pd.to_datetime(df['date'])
    since = datetime.datetime.now() - datetime.timedelta(days=WINDOW)
    df = df[df['date'] >= since].sort_values(by='date') # Sort by date for correct diff/log return calculation

    if df.empty:
        print(f"No trades data found within the last {WINDOW} days.")
        return

    log = []
    if 'assets' not in cfg or not isinstance(cfg.get('assets'), dict):
        print("Error: 'assets' key missing or not a dictionary in config.")
        return

    for tkr, grp in df.groupby('ticker'):
        if len(grp) < 2: continue # Need at least two points to calculate return
        sr = roll_sharpe(grp['price'].values)
        asset_config = cfg['assets'].get(tkr)

        if not asset_config or 'max_position_size' not in asset_config:
            print(f"Warning: Config or 'max_position_size' missing for ticker {tkr}. Skipping.")
            continue

        # --- Slippage Penalty --- >8bp -> -15% size
        # Ensure slippage_bp column exists and has non-null values before calculating mean
        if 'slippage_bp' in grp.columns and not grp['slippage_bp'].isnull().all():
            avg_slip = grp['slippage_bp'].mean()
            if avg_slip > SLIPPAGE_PENALTY_THRESHOLD_BP:
                original_size = asset_config['max_position_size']
                # Reduce size by 15%, ensuring it doesn't go below a minimum (e.g., 10000)
                asset_config['max_position_size'] = max(10000, int(original_size * (1 - SLIPPAGE_PENALTY_FACTOR)))
                log.append(f" {tkr} avg slippage {avg_slip:.1f} bp > {SLIPPAGE_PENALTY_THRESHOLD_BP} bp → size reduced from {original_size} to {asset_config['max_position_size']} (-{SLIPPAGE_PENALTY_FACTOR*100}%)")
        else:
             print(f"Warning: 'slippage_bp' data missing or all null for {tkr}. Skipping slippage penalty.")

        # --- End Slippage Penalty ---

        current_size = asset_config['max_position_size'] # Use potentially adjusted size
        new_size = current_size # Default to current size

        if sr < 0.5:
            new_size = max(100000, current_size * (1 - STEP))
            if new_size != current_size:
                log.append(f" {tkr} Sharpe {sr:.2f} < 0.5 → size down {STEP*100:.0f}% to ${new_size:,.0f}")
        elif sr > 1.5:
            new_size = min(1_500_000, current_size * (1 + STEP))
            if new_size != current_size:
                log.append(f" {tkr} Sharpe {sr:.2f} > 1.5 → size up {STEP*100:.0f}% to ${new_size:,.0f}")

        cfg['assets'][tkr]['max_position_size'] = int(new_size) # Update config with new size (as int)

    if log:
        save_cfg(cfg)
        print("Config updated based on Sharpe tuning and slippage.")
        for l in log:
            print(l)
            sn.slack(l) # Send notification via slack helper
    else:
        print("No tuning adjustments made based on current Sharpe ratios and slippage.")

if __name__ == '__main__':
    # --- Running the Tuner ---_tuner
    # This script is designed to be run periodically (e.g., daily, weekly).
    # It should be scheduled using an external tool like cron (Linux/macOS) 
    # or Task Scheduler (Windows), or a cloud equivalent like Cloud Scheduler.
    # Example cron job (runs daily at 1 AM):
    # 0 1 * * * /usr/bin/python /path/to/dynasty-engine/sharpe_tuner.py >> /path/to/logs/sharpe_tuner.log 2>&1
    print(f"Running Sharpe Tuner (Window: {WINDOW} days, Step: {STEP*100}%, Slippage Threshold: {SLIPPAGE_PENALTY_THRESHOLD_BP} bp)")
    tune()
