#!/usr/bin/env python3
"""
Statistical utilities for benchmark analysis.
"""
import math
import statistics
from typing import Dict, Any, List


def summarize(values: List[float]) -> Dict[str, float]:
    """Compute summary statistics."""
    if not values:
        return {"count": 0, "mean": 0, "median": 0, "stdev": 0, "min": 0, "max": 0}

    return {
        "count": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0,
        "min": min(values),
        "max": max(values),
    }


def welch_ttest(a: List[float], b: List[float]) -> Dict[str, Any]:
    """Welch's t-test for unequal variances.

    Returns t-statistic, degrees of freedom, and p-value.
    """
    if len(a) < 2 or len(b) < 2:
        return {"t_stat": 0, "df": 0, "p_value": 1.0, "significant": False}

    mean_a = statistics.mean(a)
    mean_b = statistics.mean(b)
    var_a = statistics.variance(a)
    var_b = statistics.variance(b)
    n_a = len(a)
    n_b = len(b)

    # Welch-Satterthwaite degrees of freedom
    numerator = (var_a / n_a + var_b / n_b) ** 2
    denominator = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
    df = numerator / denominator if denominator > 0 else 1

    # t-statistic
    se = math.sqrt(var_a / n_a + var_b / n_b)
    t_stat = (mean_a - mean_b) / se if se > 0 else 0

    # Approximate p-value (two-tailed) using simple approximation
    # For production, use scipy.stats.t.sf
    p_value = _approx_p_value(abs(t_stat), df)

    return {
        "t_stat": t_stat,
        "df": df,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "mean_diff": mean_a - mean_b,
    }


def _approx_p_value(t: float, df: float) -> float:
    """Rough approximation of two-tailed p-value.

    Uses the fact that for df > 30, t-distribution ≈ normal.
    For smaller df, we use a simple polynomial correction.
    """
    # Normal approximation: p ≈ 2 * (1 - Phi(t))
    # Phi approximation using error function
    import math

    # Adjust t for small df
    if df < 30:
        t = t * math.sqrt(df / 30)

    # Approximate CDF of standard normal at -t
    # Abramowitz & Stegun approximation
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1 if t >= 0 else -1
    x = abs(t) / math.sqrt(2)

    t_approx = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t_approx + a4) * t_approx) + a3) * t_approx + a2) * t_approx + a1) * t_approx * math.exp(-x * x)

    cdf = 0.5 * (1.0 + sign * y)
    return 2 * (1 - cdf)
