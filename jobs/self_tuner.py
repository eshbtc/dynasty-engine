# Dynasty Engine Phase 3 - Self-Tuner Module (self_tuner.py)

import sqlite3
import datetime
import yaml
import os
import random

# Load and Save Config
CONFIG_PATH = 'config.yaml'

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f)

# Self-Tuner Engine
def self_tune_config():
    config = load_config()
    conn = sqlite3.connect('trade_tracker.db')
    cursor = conn.cursor()

    df = pd.read_sql_query("SELECT * FROM trades WHERE date >= ?", conn,
                           params=[(datetime.datetime.now() - datetime.timedelta(days=30)).isoformat()])
    conn.close()

    if df.empty:
        print("[Self-Tuner] No trades in past 30 days. Skipping tuning.")
        return

    asset_tuning_log = []

    for asset, settings in config['assets'].items():
        asset_df = df[df['ticker'] == asset]
        if asset_df.empty:
            continue

        pnl = asset_df['price'].diff().fillna(0).sum()
        win_rate = (asset_df['price'].diff() > 0).mean() * 100

        print(f"[Self-Tuner] {asset}: PnL={pnl:.2f}, Win Rate={win_rate:.1f}%")

        # Adjust thresholds if performance is poor
        if win_rate < 50 or pnl < 0:
            if settings['strategy'] == 'leap_puts':
                settings['entry_iv_rank_threshold'] = min(50, settings.get('entry_iv_rank_threshold', 30) + 5)
            elif settings['strategy'] == 'swing_volatility':
                settings['entry_volatility_threshold'] = min(80, settings.get('entry_volatility_threshold', 50) + 5)
            settings['max_position_size'] = max(100000, settings['max_position_size'] - 50000)
            asset_tuning_log.append(f"Decreased position size and increased entry threshold for {asset} due to underperformance.")

        # Reinforce good behavior
        elif win_rate > 70 and pnl > 10000:
            settings['max_position_size'] = min(1000000, settings['max_position_size'] + 50000)
            asset_tuning_log.append(f"Increased position size for {asset} due to strong performance.")

    save_config(config)

    # Log tuning decisions
    with open('tuning_log.txt', 'a') as log:
        for line in asset_tuning_log:
            log.write(f"{datetime.datetime.now().isoformat()} - {line}\n")

    print("[Self-Tuner] Config tuning complete.")


if __name__ == "__main__":
    # --- Running the Tuner ---
    # This script is designed to be run periodically (e.g., weekly, monthly).
    # It should be scheduled using an external tool like cron (Linux/macOS) 
    # or Task Scheduler (Windows), or a cloud equivalent like Cloud Scheduler.
    # Example cron job (runs on the 1st of every month at 2 AM):
    # 0 2 1 * * /usr/bin/python /path/to/dynasty-engine/self_tuner.py >> /path/to/logs/self_tuner.log 2>&1
    import pandas as pd
    self_tune_config()


# === Summary ===
# Reads last 30 days of trades from SQLite
# Calculates PnL and Win Rate by asset
# Adjusts thresholds and max position size up/down based on performance
# Writes changes to config.yaml
# Logs tuning actions into tuning_log.txt

# === Integration Option ===
# Schedule this script via Cloud Scheduler to run weekly or monthly
# Or call `self_tune_config()` inside dynasty_engine.py cycle once a week

# === Phase 3: COMPLETE 
# monthly_reporter.py
# trade_commentary.py
# multi_asset_manager.py
# auto_hedger.py
# self_tuner.py 