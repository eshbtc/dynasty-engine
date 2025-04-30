import csv, sys
from collections import defaultdict


def backtest_file(csv_path, strategy_func):
    import logging
    logger = logging.getLogger(__name__)
    pnl, trades = 0.0, []
    try:
        with open(csv_path) as f:
            rdr = csv.DictReader(f)
            rows = list(rdr)
    except Exception as e:
        logger.error(f"Failed to open/read {csv_path}: {e}")
        return 0.0, []
    for i, row in enumerate(rows):
        try:
            price = float(row['close'])
            iv = float(row.get('iv_rank', 50))
            action = strategy_func(price, iv)
            if action:
                trades.append((row['date'], action, price))
                pnl += price * (1 if action == 'SELL' else -1)
        except Exception as e:
            logger.warning(f"Skipping row {i} due to error: {e}")
            continue
    return pnl, trades

# example stub strategy
if __name__ == "__main__":
    ticker, start, end, path = sys.argv[1:5]
    def strat(p, iv):
        return 'BUY' if iv<30 else None
    result = backtest_file(path, strat)
    print(result)