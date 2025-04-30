import sqlite3
import logging
import datetime

logger = logging.getLogger(__name__)

class DbManager:
    def __init__(self, db_name='dynasty_trades.db'):
        """Initializes the DbManager and connects to the SQLite database."""
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
            logger.info(f"Successfully connected to database: {self.db_name}")
            self._create_tables()
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database {self.db_name}: {e}", exc_info=True)
            self.conn = None # Ensure connection is None if setup fails

    def _create_tables(self):
        """Creates the necessary database tables if they don't exist."""
        if not self.conn:
            logger.error("Cannot create tables: No database connection.")
            return
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ticker TEXT NOT NULL,
                    action TEXT NOT NULL, -- 'BUY' or 'SELL'
                    quantity INTEGER NOT NULL,
                    strategy_price REAL, -- Price used by strategy for decision
                    avg_fill_price REAL, -- Actual execution price
                    commission REAL,
                    slippage_bp REAL, -- Slippage in basis points
                    status TEXT -- e.g., 'Filled', 'Cancelled', 'Timeout'
                )
            ''')
            self.conn.commit()
            logger.info("Ensured 'trades' table exists.")
        except sqlite3.Error as e:
            logger.error(f"Error creating 'trades' table: {e}", exc_info=True)

    def save_trade(self, trade_data: dict):
        """Saves trade execution details to the database."""
        if not self.conn:
            logger.error("Cannot save trade: No database connection.")
            return False
        if not trade_data or 'ticker' not in trade_data:
            logger.warning("Attempted to save invalid trade data.")
            return False

        sql = '''
            INSERT INTO trades (timestamp, ticker, action, quantity, strategy_price, avg_fill_price, commission, slippage_bp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        try:
            ts = datetime.datetime.now()
            params = (
                ts,
                trade_data.get('ticker'),
                trade_data.get('action'),
                trade_data.get('quantity'),
                trade_data.get('strategy_price'),
                trade_data.get('avg_fill_price'),
                trade_data.get('commission'),
                trade_data.get('slippage_bp'),
                trade_data.get('status', 'Unknown') # Default status if missing
            )
            self.cursor.execute(sql, params)
            self.conn.commit()
            logger.info(f"Successfully saved trade for {trade_data.get('ticker')} to database.")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error saving trade for {trade_data.get('ticker')} to database: {e}", exc_info=True)
            self.conn.rollback() # Rollback on error
            return False

    def close(self):
        """Closes the database connection."""
        if self.conn:
            try:
                self.conn.close()
                logger.info(f"Database connection {self.db_name} closed.")
            except sqlite3.Error as e:
                logger.error(f"Error closing database connection {self.db_name}: {e}", exc_info=True)
        self.conn = None
        self.cursor = None

# Example usage (optional - for testing)
if __name__ == '__main__':
    # Setup basic logging for testing this module directly
    log_formatter_main = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logger_main = logging.getLogger()
    logger_main.setLevel(logging.INFO)
    stream_handler_main = logging.StreamHandler()
    stream_handler_main.setFormatter(log_formatter_main)
    if not logger_main.hasHandlers():
        logger_main.addHandler(stream_handler_main)

    logger.info("Testing DbManager...")
    db = DbManager() # Uses default 'dynasty_trades.db'

    if db.conn:
        # Example trade data
        test_trade = {
            'ticker': 'TEST',
            'action': 'BUY',
            'quantity': 100,
            'strategy_price': 150.00,
            'avg_fill_price': 150.05,
            'commission': 1.00,
            'slippage_bp': 3.33,
            'status': 'Filled'
        }
        success = db.save_trade(test_trade)
        logger.info(f"Test trade save attempt successful: {success}")

        # Example failed trade
        failed_trade = {
            'ticker': 'FAIL',
            'action': 'SELL',
            'quantity': 50,
            'strategy_price': 200.00,
            'status': 'Timeout'
        }
        success_fail = db.save_trade(failed_trade)
        logger.info(f"Test failed trade save attempt successful: {success_fail}")

        # Close connection when done
        db.close()
    else:
        logger.error("Failed to initialize DbManager for testing.")
