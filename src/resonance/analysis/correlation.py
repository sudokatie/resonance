"""Correlation analysis for finding relationships between metrics."""

from dataclasses import dataclass
from itertools import combinations
from typing import Optional

import pandas as pd
from scipy.stats import spearmanr


@dataclass
class CorrelationResult:
    """Result of a correlation calculation."""

    metric1: str
    metric2: str
    correlation: float
    p_value: float
    sample_size: int
    lag_days: int
    confidence: str


def calculate_confidence(r: float, p: float, n: int) -> str:
    """Calculate confidence level based on correlation stats.

    Args:
        r: Correlation coefficient
        p: P-value
        n: Sample size

    Returns:
        Confidence level: 'high', 'medium', 'low', or 'none'
    """
    if n >= 50 and p < 0.01 and abs(r) >= 0.5:
        return "high"
    elif n >= 30 and p < 0.05 and abs(r) >= 0.3:
        return "medium"
    elif n >= 14 and p < 0.05 and abs(r) >= 0.3:
        return "low"
    return "none"


def calculate_correlation(
    df: pd.DataFrame, m1: str, m2: str, lag: int = 0, min_days: int = 14
) -> Optional[CorrelationResult]:
    """Calculate Spearman correlation between two metrics.

    Args:
        df: DataFrame with metrics as columns, date index
        m1: First metric name
        m2: Second metric name
        lag: Days to lag m2 (positive = m2 shifted into future)
        min_days: Minimum days of overlapping data required

    Returns:
        CorrelationResult or None if insufficient data
    """
    if m1 not in df.columns or m2 not in df.columns:
        return None

    x = df[m1]
    # Shift m2: positive lag means we're looking at tomorrow's m2 vs today's m1
    y = df[m2].shift(-lag) if lag > 0 else df[m2]

    # Align and drop NaN
    valid = pd.concat([x, y], axis=1).dropna()
    if len(valid) < min_days:
        return None

    r, p = spearmanr(valid.iloc[:, 0], valid.iloc[:, 1])
    confidence = calculate_confidence(r, p, len(valid))

    return CorrelationResult(
        metric1=m1,
        metric2=m2,
        correlation=float(r),
        p_value=float(p),
        sample_size=len(valid),
        lag_days=lag,
        confidence=confidence,
    )


def find_all_correlations(
    df: pd.DataFrame,
    max_lag: int = 1,
    min_correlation: float = 0.3,
    p_threshold: float = 0.05,
    min_days: int = 14,
) -> list[CorrelationResult]:
    """Find all significant correlations between metrics.

    Args:
        df: DataFrame with metrics as columns, date index
        max_lag: Maximum lag days to check (0 to max_lag inclusive)
        min_correlation: Minimum absolute correlation to include
        p_threshold: Maximum p-value to include
        min_days: Minimum days of overlapping data required

    Returns:
        List of CorrelationResults sorted by absolute correlation (descending)
    """
    results = []
    metrics = [c for c in df.columns if c != "date"]

    for m1, m2 in combinations(metrics, 2):
        for lag in range(max_lag + 1):
            result = calculate_correlation(df, m1, m2, lag, min_days=min_days)
            if result and result.confidence != "none":
                if (
                    abs(result.correlation) >= min_correlation
                    and result.p_value < p_threshold
                ):
                    results.append(result)

    return sorted(results, key=lambda x: abs(x.correlation), reverse=True)


def apply_bonferroni(
    results: list[CorrelationResult], num_tests: int
) -> list[CorrelationResult]:
    """Apply Bonferroni correction for multiple testing.

    Args:
        results: List of correlation results
        num_tests: Total number of tests performed

    Returns:
        Filtered list with only results passing corrected threshold
    """
    if num_tests <= 0:
        return results
    return [r for r in results if r.p_value * num_tests < 0.05]
