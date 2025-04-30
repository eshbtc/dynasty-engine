"""Utility functions for building IBKR Option contracts and common option helpers."""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Tuple

from ib_insync import Option

__all__ = [
    "next_friday",
    "build_option_contract",
    "build_strangle_contracts",
    "build_straddle_contracts",
]


def next_friday(days_out: int = 7) -> str:
    """Return expiry string (YYYYMMDD) for the Friday at least *days_out* ahead.

    IBKR expects option expiry in YYYYMMDD format. We walk forward until the
    next Friday to standardise weekly expiries. For monthlies, increase
    *days_out* (e.g., 30).
    """
    d = date.today() + timedelta(days=days_out)
    # Friday is weekday == 4
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d.strftime("%Y%m%d")


def build_option_contract(
    symbol: str,
    underlying_price: float,
    *,
    right: str = "C",
    strike_offset_pct: float = 0.05,
    days_out: int = 7,
    exchange: str = "SMART",
) -> Option:
    """Create a single option *Option* contract.

    Parameters
    ----------
    symbol : str
        Underlying ticker, e.g., "MSTR".
    underlying_price : float
        Latest mid price of underlying used to choose strike
        when *strike* is not explicitly supplied.
    right : str, default "C"
        "C" for Call, "P" for Put.
    strike_offset_pct : float, default 0.05
        If strike not specified, take underlying_price * (1±strike_offset_pct).
    days_out : int, default 7
        Distance to expiry in days — finds the next Friday ≥ today+days_out.
    exchange : str, default "SMART"
        IBKR exchange routing.
    """
    expiry = next_friday(days_out)
    if right.upper() == "C":
        strike = math.ceil(underlying_price * (1 + strike_offset_pct))
    else:
        strike = math.floor(underlying_price * (1 - strike_offset_pct))
    return Option(symbol, expiry, strike, right.upper(), exchange)


def build_strangle_contracts(
    symbol: str,
    underlying_price: float,
    *,
    strike_offset_pct: float = 0.05,
    days_out: int = 7,
    exchange: str = "SMART",
) -> Tuple[Option, Option]:
    """Return (call, put) option contracts forming an ATM±offset short strangle."""
    call = build_option_contract(
        symbol,
        underlying_price,
        right="C",
        strike_offset_pct=strike_offset_pct,
        days_out=days_out,
        exchange=exchange,
    )
    put = build_option_contract(
        symbol,
        underlying_price,
        right="P",
        strike_offset_pct=strike_offset_pct,
        days_out=days_out,
        exchange=exchange,
    )
    return call, put


def build_straddle_contracts(
    symbol: str,
    underlying_price: float,
    *,
    days_out: int = 7,
    exchange: str = "SMART",
) -> Tuple[Option, Option]:
    """Return (call, put) ATM straddle (same strike)."""
    expiry = next_friday(days_out)
    strike = round(underlying_price)  # ATM approx

    call = Option(symbol, expiry, strike, "C", exchange)
    put = Option(symbol, expiry, strike, "P", exchange)
    return call, put
