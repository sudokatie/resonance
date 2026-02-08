"""Trend analysis for week/month over week/month comparisons."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Tuple

import pandas as pd


@dataclass
class TrendResult:
    """Result of a trend comparison."""

    metric: str
    period1_mean: float
    period2_mean: float
    change_pct: float
    direction: str  # 'up', 'down', 'stable'


def compare_periods(
    df: pd.DataFrame,
    metric: str,
    p1: Tuple[str, str],
    p2: Tuple[str, str],
    direction_threshold: float = 5.0,
) -> Optional[TrendResult]:
    """Compare metric values between two time periods.

    Args:
        df: DataFrame with metrics as columns, date index
        metric: Metric name to compare
        p1: First period as (start_date, end_date) strings
        p2: Second period as (start_date, end_date) strings
        direction_threshold: Percentage change threshold for up/down

    Returns:
        TrendResult or None if insufficient data
    """
    if metric not in df.columns:
        return None

    series = df[metric].dropna()
    if len(series) == 0:
        return None

    # Convert index to string for comparison if needed
    try:
        idx = pd.to_datetime(series.index).strftime("%Y-%m-%d")
    except Exception:
        idx = series.index.astype(str)

    series_with_str_idx = series.copy()
    series_with_str_idx.index = idx

    p1_data = series_with_str_idx[(idx >= p1[0]) & (idx <= p1[1])]
    p2_data = series_with_str_idx[(idx >= p2[0]) & (idx <= p2[1])]

    if len(p1_data) < 3 or len(p2_data) < 3:
        return None

    m1 = p1_data.mean()
    m2 = p2_data.mean()

    if m1 == 0:
        pct = 0.0 if m2 == 0 else 100.0  # Handle zero baseline
    else:
        pct = ((m2 - m1) / abs(m1)) * 100

    if pct > direction_threshold:
        direction = "up"
    elif pct < -direction_threshold:
        direction = "down"
    else:
        direction = "stable"

    return TrendResult(
        metric=metric,
        period1_mean=float(m1),
        period2_mean=float(m2),
        change_pct=float(pct),
        direction=direction,
    )


def week_over_week(
    df: pd.DataFrame, metric: str, reference_date: Optional[date] = None
) -> Optional[TrendResult]:
    """Compare this week to last week.

    Args:
        df: DataFrame with metrics as columns, date index
        metric: Metric name to compare
        reference_date: Date to use as "today" (defaults to actual today)

    Returns:
        TrendResult or None if insufficient data
    """
    today = reference_date or date.today()
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)

    p1 = (last_week_start.isoformat(), last_week_end.isoformat())
    p2 = (this_week_start.isoformat(), today.isoformat())

    return compare_periods(df, metric, p1, p2)


def month_over_month(
    df: pd.DataFrame, metric: str, reference_date: Optional[date] = None
) -> Optional[TrendResult]:
    """Compare this month to last month.

    Args:
        df: DataFrame with metrics as columns, date index
        metric: Metric name to compare
        reference_date: Date to use as "today" (defaults to actual today)

    Returns:
        TrendResult or None if insufficient data
    """
    today = reference_date or date.today()

    # This month start
    this_month_start = today.replace(day=1)

    # Last month start and end
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    p1 = (last_month_start.isoformat(), last_month_end.isoformat())
    p2 = (this_month_start.isoformat(), today.isoformat())

    return compare_periods(df, metric, p1, p2)


def find_all_trends(
    df: pd.DataFrame, reference_date: Optional[date] = None
) -> dict[str, list[TrendResult]]:
    """Find week-over-week and month-over-month trends for all metrics.

    Args:
        df: DataFrame with metrics as columns, date index
        reference_date: Date to use as "today" (defaults to actual today)

    Returns:
        Dict with 'weekly' and 'monthly' keys containing trend lists
    """
    weekly = []
    monthly = []

    for metric in df.columns:
        if metric == "date":
            continue

        wow = week_over_week(df, metric, reference_date)
        if wow:
            weekly.append(wow)

        mom = month_over_month(df, metric, reference_date)
        if mom:
            monthly.append(mom)

    return {"weekly": weekly, "monthly": monthly}
