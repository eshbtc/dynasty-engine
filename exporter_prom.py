from prometheus_client import start_http_server, Gauge
import time, sqlite3
import numpy as np

pnl_gauge = Gauge('dynasty_cumulative_pnl', 'Cumulative PnL')
trade_count = Gauge('dynasty_trade_total', 'Total Trades')
max_price_gauge = Gauge('dynasty_max_trade_price', 'Maximum Price Recorded in Trades')
# Define VaR Gauges
var5 = Gauge('dynasty_var_5p', 'Value at Risk 95% over last 60 trades (price % change)', ['asset'])
var1 = Gauge('dynasty_var_1p', 'Value at Risk 99% over last 60 trades (price % change)', ['asset'])
# RL analytics gauges
rl_pnl = Gauge('dynasty_rl_monthly_pnl', 'RL Agent Monthly PnL')
rl_drawdown = Gauge('dynasty_rl_drawdown', 'RL Agent Drawdown')
rl_target = Gauge('dynasty_rl_target_achieved', 'RL Agent Target Achieved (1=Yes, 0=No)')
open_pos_count = Gauge('dynasty_open_positions', 'Current Open Positions')
stop_loss_count = Gauge('dynasty_stop_loss_events', 'Recent Stop-Loss Events')
# Backtest metrics
backtest_pnl = Gauge('dynasty_backtest_pnl', 'Latest Backtest PnL')
backtest_sharpe = Gauge('dynasty_backtest_sharpe', 'Latest Backtest Sharpe')
backtest_drawdown = Gauge('dynasty_backtest_max_drawdown', 'Latest Backtest Max Drawdown')
backtest_win_rate = Gauge('dynasty_backtest_win_rate', 'Latest Backtest Win Rate')

def collect_metrics():
    conn = sqlite3.connect('trade_tracker.db')
    cur = conn.cursor()

    cur.execute("SELECT SUM(price) FROM trades")
    pnl = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM trades")
    count = cur.fetchone()[0]

    cur.execute('SELECT MAX(price) FROM trades')
    max_px = cur.fetchone()[0] or 0

    pnl_gauge.set(pnl)
    trade_count.set(count)
    max_price_gauge.set(max_px)

    # --- VaR Calculation per Asset ---
    try:
        # Get distinct tickers from the trades table
        cur.execute("SELECT DISTINCT ticker FROM trades")
        tickers = [row[0] for row in cur.fetchall()]

        for ticker in tickers:
            # Get the last 60 non-zero prices for the current ticker
            cur.execute("SELECT price FROM trades WHERE ticker = ? AND price > 0 ORDER BY date DESC LIMIT 60", (ticker,))
            prices = [r[0] for r in cur.fetchall()][::-1] # Fetch and reverse to get chronological order

            if len(prices) > 10: # Need sufficient data points for percentile calculation
                prices_array = np.array(prices)
                # Calculate simple percentage returns: (p_t - p_{t-1}) / p_{t-1}
                returns = np.diff(prices_array) / prices_array[:-1]

                # Calculate VaR (Value at Risk) - negative of the percentile for loss representation
                # VaR 95% (5th percentile of returns)
                var_95 = -np.percentile(returns, 5)
                # VaR 99% (1st percentile of returns)
                var_99 = -np.percentile(returns, 1)

                # Set the gauges, labeled by the asset ticker
                # Multiply by 100 to express as percentage, round to 3 decimal places
                var5.labels(asset=ticker).set(round(var_95 * 100, 3))
                var1.labels(asset=ticker).set(round(var_99 * 100, 3))
                # print(f"Calculated VaR for {ticker}: 5%={var_95*100:.3f}%, 1%={var_99*100:.3f}%") # Optional logging
            else:
                # Optionally set to a default value like 0 or NaN if not enough data
                var5.labels(asset=ticker).set(0) # Or use float('nan') if preferred
                var1.labels(asset=ticker).set(0)
                # print(f"Not enough data points ({len(prices)}) to calculate VaR for {ticker}.")

    except sqlite3.Error as e:
        print(f"Database error during VaR calculation: {e}")
    except Exception as e:
        print(f"Error during VaR calculation: {e}")
    # --- End VaR Calculation ---

    conn.close()

    # --- RL Analytics Export ---
    try:
        import json, os, glob
        # RL status
        rl_path = 'data/rl_status.json'
        if os.path.exists(rl_path):
            with open(rl_path) as f:
                rl = json.load(f)
            rl_pnl.set(rl.get('monthly_pnl', 0))
            rl_drawdown.set(rl.get('drawdown', 0))
            rl_target.set(1 if rl.get('target_achieved') else 0)
        # Open positions
        pos_path = 'data/open_positions.json'
        if os.path.exists(pos_path):
            with open(pos_path) as f:
                pos = json.load(f)
            open_pos_count.set(len(pos.get('positions', [])))
        # Stop-loss events
        sl_path = 'data/stop_loss_events.json'
        if os.path.exists(sl_path):
            with open(sl_path) as f:
                sl = json.load(f)
            stop_loss_count.set(len(sl.get('events', [])))
        # Latest backtest (by mtime)
        bt_dir = 'data/backtests'
        if os.path.isdir(bt_dir):
            files = sorted(glob.glob(os.path.join(bt_dir, '*.json')), key=os.path.getmtime, reverse=True)
            if files:
                with open(files[0]) as f:
                    bt = json.load(f)
                s = bt.get('summary', {})
                backtest_pnl.set(s.get('pnl', 0))
                backtest_sharpe.set(s.get('sharpe', 0))
                backtest_drawdown.set(s.get('max_drawdown', 0))
                backtest_win_rate.set(s.get('win_rate', 0))
    except Exception as e:
        print(f"Error exporting RL/backtest metrics: {e}")

if __name__ == '__main__':
    # --- Running the Exporter ---
    # This script needs to run as a separate, persistent background process
    # alongside the main dynasty_engine.py.
    # 
    # How to run:
    # 1. Ensure prometheus_client is installed (`pip install prometheus-client`).
    # 2. Run directly: `python exporter_prom.py`
    # 3. For persistence (recommended), use a process manager like:
    #    - `supervisor`: Configure a program section for this script.
    #    - `systemd`: Create a service unit file.
    #    - `pm2` (if Node.js is available): `pm2 start exporter_prom.py --name dynasty-prom-exporter --interpreter python`
    #    - `docker`: Include it in your Docker Compose setup as a separate service.
    #
    # Ensure the port (default 8000) is accessible to your Prometheus server.
    # Add the exporter's address (e.g., <host>:8000) to your Prometheus scrape configuration.
    #
    port = 8000
    print(f"Starting Prometheus exporter on port {port}")
    start_http_server(port)
    print("Exporter started. Collecting metrics...")
    # Keep the script running and update metrics periodically
    while True:
        collect_metrics()
        # Adjust sleep time based on desired metric update frequency
        time.sleep(60) # Update metrics every 60 seconds