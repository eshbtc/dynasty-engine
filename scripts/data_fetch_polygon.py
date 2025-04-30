#!/usr/bin/env python3
"""Download daily OHLC + IV Rank from Polygon.io and save parquet.

Example:
    python scripts/data_fetch_polygon.py --symbol MSTR --start 2022-01-01 --end 2024-01-01 --out data/mstr_raw.parquet

IV Rank endpoint isn't public on Polygon; you'll need a separate source.
Here we store a placeholder NaN that can be filled by feature_engineering.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
from typing import Iterator

import pandas as pd
from polygon import RESTClient
from tqdm import tqdm


def parse_args():
    p = argparse.ArgumentParser(description="Fetch OHLC from Polygon.io")
    p.add_argument("--symbol", required=True, help="Ticker symbol e.g. MSTR")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--out", required=True, help="Output parquet path")
    p.add_argument("--api-key", help="Polygon API key (else POLYGON_KEY env)")
    return p.parse_args()


def daterange(start: dt.date, end: dt.date) -> Iterator[dt.date]:
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def main() -> None:
    args = parse_args()
    api_key = args.api_key or os.getenv("POLYGON_KEY")
    if not api_key:
        raise SystemExit("Polygon API key missing. Set POLYGON_KEY or pass --api-key")

    client = RESTClient(api_key)
    start_d = dt.datetime.strptime(args.start, "%Y-%m-%d").date()
    end_d = dt.datetime.strptime(args.end, "%Y-%m-%d").date()

    rows = []
    for day in tqdm(list(daterange(start_d, end_d))):
        agg = client.get_aggs(
            ticker=args.symbol.upper(),
            multiplier=1,
            timespan="day",
            from_=day.isoformat(),
            to=day.isoformat(),
            limit=1,
        )
        if agg and agg.results:
            r = agg.results[0]
            rows.append(
                {
                    "date": day.isoformat(),
                    "price": r["c"],
                    "open": r["o"],
                    "high": r["h"],
                    "low": r["l"],
                    "volume": r["v"],
                    "iv_rank": None,  # placeholder
                }
            )

    if not rows:
        raise SystemExit("No data fetched; check symbol and dates")

    df = pd.DataFrame(rows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Saved {len(df)} rows → {out}")


if __name__ == "__main__":
    main()
