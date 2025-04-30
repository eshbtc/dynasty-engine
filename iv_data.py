import os, requests, datetime, math, logging

POLY_KEY = os.getenv("POLYGON_KEY")
logger = logging.getLogger(__name__)


def iv_rank_polygon(ticker: str, days: int = 252):
    if not POLY_KEY:
        logger.error(f"[iv_rank_polygon] POLYGON_KEY not set. Skipping IV fetch for {ticker}.")
        return None
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{(datetime.date.today()-datetime.timedelta(days)).isoformat()}/{datetime.date.today().isoformat()}?adjusted=true&apiKey={POLY_KEY}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        ivs = [c.get("vwap", 0) for c in data.get("results", []) if "vwap" in c]
        if len(ivs) < 10:
            logger.warning(f"[iv_rank_polygon] Insufficient IV data for {ticker}. Skipping asset.")
            return None
        todays_iv = ivs[-1]
        rank = sum(1 for v in ivs if v < todays_iv)/len(ivs)*100
        return round(rank, 1)
    except Exception as e:
        logger.error(f"[iv_rank_polygon] Error fetching IV for {ticker}: {e}")
        return None


def crypto_realized_vol(symbol: str = "BTC", window: int = 30):
    if not POLY_KEY:
        logger.error(f"[crypto_realized_vol] POLYGON_KEY not set. Skipping vol fetch for {symbol}.")
        return None
    try:
        sym = "BTC-USD" if symbol == "BTC" else "ETH-USD"
        url = f"https://api.polygon.io/v2/aggs/ticker/C:{sym}/range/1/day/{(datetime.date.today()-datetime.timedelta(window)).isoformat()}/{datetime.date.today().isoformat()}?adjusted=true&apiKey={POLY_KEY}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        closes = [c["c"] for c in data.get("results", [])]
        if len(closes) < window:
            logger.warning(f"[crypto_realized_vol] Insufficient close data for {symbol}. Skipping asset.")
            return None
        log_returns = [math.log(closes[i]/closes[i-1]) for i in range(1, len(closes))]
        vol = (sum(r*r for r in log_returns)/len(log_returns))**0.5 * math.sqrt(365)*100
        return round(vol, 2)
    except Exception as e:
        logger.error(f"[crypto_realized_vol] Error fetching vol for {symbol}: {e}")
        return None