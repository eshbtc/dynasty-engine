import os, requests, datetime, math

POLY_KEY = os.getenv("POLYGON_KEY", "YOUR_POLYGON_KEY")


def iv_rank_polygon(ticker: str, days: int = 252):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{(datetime.date.today()-datetime.timedelta(days)).isoformat()}/{datetime.date.today().isoformat()}?adjusted=true&apiKey={POLY_KEY}"
    data = requests.get(url, timeout=10).json()
    ivs = [c.get("vwap", 0) for c in data.get("results", []) if "vwap" in c]
    if len(ivs) < 10:
        return None
    todays_iv = ivs[-1]
    rank = sum(1 for v in ivs if v < todays_iv)/len(ivs)*100
    return round(rank, 1)


def crypto_realized_vol(symbol: str = "BTC", window: int = 30):
    sym = "BTC-USD" if symbol == "BTC" else "ETH-USD"
    url = f"https://api.polygon.io/v2/aggs/ticker/C:{sym}/range/1/day/{(datetime.date.today()-datetime.timedelta(window)).isoformat()}/{datetime.date.today().isoformat()}?adjusted=true&apiKey={POLY_KEY}"
    data = requests.get(url, timeout=10).json()
    closes = [c["c"] for c in data.get("results", [])]
    if len(closes) < window:
        return None
    log_returns = [math.log(closes[i]/closes[i-1]) for i in range(1, len(closes))]
    vol = (sum(r*r for r in log_returns)/len(log_returns))**0.5 * math.sqrt(365)*100
    return round(vol, 2)