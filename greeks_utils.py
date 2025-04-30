"""Black–Scholes analytical greeks helpers (vanilla European options).

Uses Python stdlib (statistics.NormalDist) – no external deps. Intended for quick
risk checks, **not** pricing accuracy in illiquid markets.
"""
from __future__ import annotations

import math
from statistics import NormalDist
from typing import Literal

ND = NormalDist()

# type alias
Right = Literal["C", "P", "c", "p"]


def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:  # noqa: N802
    return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))


def _d2(S: float, K: float, T: float, r: float, sigma: float) -> float:  # noqa: N802
    return _d1(S, K, T, r, sigma) - sigma * math.sqrt(T)


def delta(S: float, K: float, T: float, r: float, sigma: float, right: Right = "C") -> float:
    """Return Black–Scholes delta.

    Parameters are spot price *S*, strike *K*, time to expiry *T* (in years),
    risk-free rate *r*, volatility *sigma* (annualised), and *right* (C/P).
    """
    d1 = _d1(S, K, T, r, sigma)
    if right.upper() == "C":
        return ND.cdf(d1)
    else:
        return ND.cdf(d1) - 1.0


def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Return vega (per 1 vol point) i.e. \partial P / \partial sigma.

    Returned in *price per 1% vol*, so divide by 100 to get per unit vol.
    """
    d1 = _d1(S, K, T, r, sigma)
    return S * ND.pdf(d1) * math.sqrt(T) / 100.0


def main() -> None:  # quick sanity check
    S = 100
    K = 100
    T = 30 / 365
    r = 0.0
    sigma = 0.5
    print("call delta", delta(S, K, T, r, sigma))
    print("put  delta", delta(S, K, T, r, sigma, right="P"))
    print("vega", vega(S, K, T, r, sigma))


if __name__ == "__main__":
    main()
