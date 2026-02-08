"""Pattern detection for weekday effects and anomalies."""

from dataclasses import dataclass
from typing import Optional

import pandas as pd
from scipy.stats import ttest_ind

# Weekday names for output
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class WeekdayPattern:
    """A weekday-specific pattern in a metric."""

    metric: str
    weekday: int
    weekday_name: str
    mean: float
    overall_mean: float
    difference_pct: float
    significant: bool


@dataclass
class Anomaly:
    """An anomalous data point."""

    date: str
    metric: str
    value: float
    z_score: float
    direction: str  # 'high' or 'low'


def find_weekday_patterns(
    df: pd.DataFrame, p_threshold: float = 0.05
) -> list[WeekdayPattern]:
    """Find significant weekday effects in metrics.

    Args:
        df: DataFrame with metrics as columns, date index
        p_threshold: P-value threshold for significance

    Returns:
        List of significant weekday patterns
    """
    results = []

    for metric in df.columns:
        if metric == "date":
            continue

        series = df[metric].dropna()
        if len(series) < 14:
            continue

        overall_mean = series.mean()
        if overall_mean == 0:
            continue  # Avoid division by zero

        # Get weekday for each date
        try:
            weekdays = pd.to_datetime(series.index).weekday
        except Exception:
            continue

        for day in range(7):
            day_values = series[weekdays == day]
            other_values = series[weekdays != day]

            if len(day_values) < 2 or len(other_values) < 2:
                continue

            _, p = ttest_ind(day_values, other_values)
            day_mean = day_values.mean()
            diff_pct = ((day_mean - overall_mean) / overall_mean) * 100

            if p < p_threshold:
                results.append(
                    WeekdayPattern(
                        metric=metric,
                        weekday=day,
                        weekday_name=WEEKDAY_NAMES[day],
                        mean=day_mean,
                        overall_mean=overall_mean,
                        difference_pct=diff_pct,
                        significant=True,
                    )
                )

    return results


def find_anomalies(
    df: pd.DataFrame, metric: str, threshold: float = 2.0
) -> list[Anomaly]:
    """Find anomalous values in a metric.

    Args:
        df: DataFrame with metrics as columns, date index
        metric: Metric name to analyze
        threshold: Z-score threshold for anomaly detection

    Returns:
        List of anomalies sorted by absolute z-score (descending)
    """
    if metric not in df.columns:
        return []

    series = df[metric].dropna()
    if len(series) < 3:
        return []

    mean = series.mean()
    std = series.std()

    if std == 0:
        return []  # Constant metric has no anomalies

    anomalies = []
    for date, value in series.items():
        z = (value - mean) / std
        if abs(z) > threshold:
            anomalies.append(
                Anomaly(
                    date=str(date)[:10],  # Format as YYYY-MM-DD
                    metric=metric,
                    value=float(value),
                    z_score=float(z),
                    direction="high" if z > 0 else "low",
                )
            )

    return sorted(anomalies, key=lambda x: abs(x.z_score), reverse=True)


def find_all_anomalies(
    df: pd.DataFrame, threshold: float = 2.0
) -> list[Anomaly]:
    """Find anomalies across all metrics.

    Args:
        df: DataFrame with metrics as columns, date index
        threshold: Z-score threshold for anomaly detection

    Returns:
        List of all anomalies sorted by absolute z-score (descending)
    """
    all_anomalies = []
    for metric in df.columns:
        if metric == "date":
            continue
        all_anomalies.extend(find_anomalies(df, metric, threshold))

    return sorted(all_anomalies, key=lambda x: abs(x.z_score), reverse=True)
