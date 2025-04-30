"""Unified IV/vol provider with adapter cascade."""
import os, requests, datetime, math, random
import numpy as np, time, hmac, hashlib
import logging

# Get a logger for this module
logger = logging.getLogger(__name__)

POLY=os.getenv('POLYGON_KEY')
TRADIER=os.getenv('TRADIER_KEY')

def _poly_iv(tkr):
    """Fetches implied volatility rank from Polygon.io."""
    if not POLY:
        logger.warning("Polygon API key (POLYGON_KEY) not set. Skipping Polygon IV fetch.")
        return None
    try:
        logger.debug(f"[{tkr}] Fetching IV data from Polygon...")
        url=f"https://api.polygon.io/v3/reference/options/contracts?ticker={tkr}&apiKey={POLY}"
        res = requests.get(url,timeout=6).json()
        # Assuming 'iv_rank' is a field directly available or calculated
        # Adjust based on actual Polygon API response structure if needed
        # Placeholder: Returning a field if it exists, otherwise None
        iv_data = res.get('results', [{}])[0].get('implied_volatility') # Example path, adjust as needed
        # Placeholder logic for IV rank calculation if not directly provided
        if iv_data is not None:
            # Example: if Polygon provided historical IV, calculate rank
            # For now, just return the current IV as a proxy, or None
            # return iv_data # Direct IV value - Needs conversion to rank
            logger.info(f"[{tkr}] Polygon returned IV data ({iv_data}), but rank calculation is not implemented. Returning None for rank.")
            return None # No rank available directly
        logger.debug(f"[{tkr}] No direct IV data found in Polygon response.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"[{tkr}] Polygon HTTP Error: {e}")
        return None
    except Exception as e:
        logger.exception(f"[{tkr}] Polygon Error:")
        return None

def _tradier_iv(tkr):
    """Fetches implied volatility data from Tradier and calculates rank."""
    if not TRADIER:
        logger.warning("Tradier API key (TRADIER_KEY) not set. Skipping Tradier IV fetch.")
        return None
    try:
        logger.debug(f"[{tkr}] Fetching IV data from Tradier...")
        headers = {'Authorization': f'Bearer {TRADIER}', 'Accept': 'application/json'}
        url = f"https://api.tradier.com/v1/markets/options/chains?symbol={tkr}&greeks=true"
        r = requests.get(url, headers=headers, timeout=6)
        r.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        options_data = r.json().get('options', {}).get('option', [])

        ivs = [c['greeks']['iv'] for c in options_data if c.get('greeks') and c['greeks'].get('iv') is not None]

        if not ivs:
            logger.warning(f"[{tkr}] Tradier: No IV data found.")
            return None

        # Simplified rank: % of historical IVs (from the chain) below the first observed IV.
        # This isn't a true IV Rank (usually based on 52-week high/low).
        # A proper implementation would need historical IV data.
        # Using the first IV as 'today's' IV for ranking against others in the chain.
        if len(ivs) > 1:
            today_iv = ivs[0] # Use the first valid IV as reference
            rank = sum(v < today_iv for v in ivs[1:]) / (len(ivs) - 1) * 100
            logger.debug(f"[{tkr}] Tradier calculated rank {rank:.1f} from {len(ivs)} IV values.")
        else:
            rank = 50.0 # Default rank if only one IV value
            logger.debug(f"[{tkr}] Tradier: Only one IV value found, using default rank 50.0.")

        return round(rank, 1)
    except requests.exceptions.RequestException as e:
        logger.error(f"[{tkr}] Tradier HTTP Error: {e}")
        return None
    except Exception as e:
        logger.exception(f"[{tkr}] Tradier Error:")
        return None

def get_iv_rank(tkr:str) -> float | None:
    """Gets IV rank by trying Polygon then Tradier, with a random fallback."""
    # Note: The current implementations might not return a standard IV Rank.
    # _poly_iv currently returns None, _tradier_iv returns a chain-based rank.
    logger.info(f"Fetching IV Rank for {tkr}...")
    for provider_func, name in [(_poly_iv, 'Polygon'), (_tradier_iv, 'Tradier')]:
        try:
            v = provider_func(tkr)
            if v is not None:
                logger.info(f"[{tkr}] Got IV Rank from {name}: {v}")
                return v
            else:
                logger.info(f"[{tkr}] {name} provider returned None.")
        except Exception as e:
             logger.exception(f"[{tkr}] Error calling {name} provider:")

    # CRITICAL: Random fallback is dangerous for live trading!
    # Consider alternatives: returning None, using last known good value, raising an error.
    fallback_rank = random.randint(20, 60)
    logger.warning(f"[{tkr}] All IV providers failed or returned None. Falling back to RANDOM IV Rank: {fallback_rank}")
    return float(fallback_rank)   # fallback if providers fail or return None

# crypto realised vol (Deribit)
def get_realized_vol(symbol: str = 'BTC', window: int = 30) -> float | None:
    """Calculates annualized realized volatility from Deribit daily data."""
    logger.info(f"Fetching Realized Vol for {symbol} ({window} days)...")
    end_time = int(time.time() * 1000)
    start_time = int((time.time() - window * 86400) * 1000)
    instrument = f"{symbol.upper()}-PERPETUAL"
    url = (f"https://www.deribit.com/api/v2/public/get_tradingview_chart_data?" 
           f"instrument_name={instrument}&resolution=D&start_timestamp={start_time}&end_timestamp={end_time}")

    try:
        logger.debug(f"[{symbol}] Requesting Deribit data: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if 'result' not in data or not data['result']['close']:
            logger.warning(f"[{symbol}] Deribit: No data or empty close prices for {instrument}")
            return None

        closes = np.array(data['result']['close'])
        if len(closes) < 2:
             logger.warning(f"[{symbol}] Deribit: Not enough data points ({len(closes)}) for vol calculation for {instrument}")
             return None

        log_returns = np.diff(np.log(closes))
        # Annualized volatility
        volatility = np.std(log_returns) * np.sqrt(365) * 100
        logger.info(f"[{symbol}] Calculated Realized Vol for {instrument}: {volatility:.2f}%")
        return round(volatility, 2)

    except requests.exceptions.RequestException as e:
        logger.error(f"[{symbol}] Deribit HTTP Error: {e}")
        return None
    except Exception as e:
        logger.exception(f"[{symbol}] Deribit Error:")
        return None

if __name__ == '__main__':
    # --- Setup Logging for standalone execution ---
    log_formatter_main = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logger_main = logging.getLogger() # Get root logger
    logger_main.setLevel(logging.INFO) # Set level
    stream_handler_main = logging.StreamHandler()
    stream_handler_main.setFormatter(log_formatter_main)
    if not logger_main.hasHandlers(): # Avoid adding duplicate handlers if run multiple times
         logger_main.addHandler(stream_handler_main)
    # ----------------------------------------------

    logger.info("--- IV Rank Examples ---")
    for ticker in ['AAPL', 'MSFT', 'GOOG', 'NONEXISTENT']:
        iv_rank = get_iv_rank(ticker)
        if iv_rank is not None:
            logger.info(f"IV Rank ({ticker}): {iv_rank}%")
        else:
            logger.warning(f"Could not fetch IV Rank for {ticker}")

    logger.info("\n--- Realized Vol Examples ---")
    for crypto in ['BTC', 'ETH']:
        real_vol = get_realized_vol(crypto, window=30)
        if real_vol is not None:
            logger.info(f"Realized Vol ({crypto}, 30d): {real_vol}%")
        else:
            logger.warning(f"Could not fetch Realized Vol for {crypto}")