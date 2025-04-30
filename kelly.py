import math

def kelly_fraction(mu: float, sigma: float, r: float = 0.0, c: float = 0.3) -> float:
    """Calculates the Kelly fraction for position sizing.

    Args:
        mu: Expected return (mean of returns).
        sigma: Standard deviation of returns (volatility).
        r: Risk-free rate (default: 0.0).
        c: Maximum fraction constraint (default: 0.3 or 30%).

    Returns:
        The calculated Kelly fraction, constrained between 0 and c.
    """
    if sigma <= 0:
        # Avoid division by zero or undefined result if volatility is zero or negative
        return 0.0

    # Calculate the raw Kelly fraction
    kelly_raw = (mu - r) / (sigma ** 2)

    # Apply constraints: fraction must be non-negative and not exceed the cap c
    kelly_constrained = min(max(kelly_raw, 0.0), c)

    return kelly_constrained

# Example usage:
if __name__ == '__main__':
    expected_return = 0.15  # 15% expected annual return
    volatility = 0.30     # 30% annual volatility
    risk_free = 0.02      # 2% risk-free rate
    max_allocation = 0.5  # Max 50% allocation constraint

    kf = kelly_fraction(expected_return, volatility, r=risk_free, c=max_allocation)
    print(f"Expected Return: {expected_return*100:.1f}%")
    print(f"Volatility: {volatility*100:.1f}%")
    print(f"Risk-Free Rate: {risk_free*100:.1f}%")
    print(f"Max Allocation Constraint: {max_allocation*100:.0f}%")
    print(f"Calculated Kelly Fraction: {kf*100:.2f}%")

    # Example with zero volatility
    kf_zero_vol = kelly_fraction(0.10, 0.0)
    print(f"\nKelly Fraction (Zero Volatility): {kf_zero_vol*100:.2f}%")

    # Example with negative expected return relative to risk-free rate
    kf_neg_edge = kelly_fraction(0.01, 0.20, r=0.02)
    print(f"Kelly Fraction (Negative Edge): {kf_neg_edge*100:.2f}%")