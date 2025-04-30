from prometheus_client import start_http_server, Gauge
import time, sqlite3
import numpy as np

pnl_gauge = Gauge('dynasty_cumulative_pnl', 'Cumulative PnL')
trade_count = Gauge('dynasty_trade_total', 'Total Trades')
max_price_gauge = Gauge('dynasty_max_trade_price', 'Maximum Price Recorded in Trades')
# Define VaR Gauges
var5 = Gauge('dynasty_var_5p', 'Value at Risk 95% over last 60 trades (price % change)', ['asset'])
var1 = Gauge('dynasty_var_1p', 'Value at Risk 99% over last 60 trades (price % change)', ['asset'])

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