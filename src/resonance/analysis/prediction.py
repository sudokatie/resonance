"""Prediction models for time series forecasting.

Provides simple forecasting based on historical patterns:
- Linear trend extrapolation
- Moving average forecasting
- Correlation-based "if X then Y" predictions
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np


@dataclass
class Forecast:
    """A single metric forecast."""

    metric: str
    date: date
    predicted_value: float
    confidence: float  # 0-1
    method: str  # 'linear', 'moving_avg', 'correlation'
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


@dataclass
class ConditionalPrediction:
    """Prediction based on correlation: 'If X, expect Y'."""

    cause_metric: str
    effect_metric: str
    cause_value: float
    expected_effect: float
    confidence: float
    lag_days: int
    relationship: str  # 'positive', 'negative', 'none'
    insight: str


@dataclass
class PredictionModel:
    """Container for trained prediction parameters."""

    metric: str
    method: str
    slope: Optional[float] = None
    intercept: Optional[float] = None
    window_size: int = 7
    last_values: List[float] = field(default_factory=list)
    std_dev: float = 0.0


def fit_linear_trend(
    series: pd.Series, min_points: int = 7
) -> Optional[PredictionModel]:
    """Fit a linear trend to the time series.

    Args:
        series: Time series with datetime index
        min_points: Minimum data points required

    Returns:
        PredictionModel or None if insufficient data
    """
    series = series.dropna()
    if len(series) < min_points:
        return None

    # Convert dates to numeric (days from start)
    x = np.arange(len(series))
    y = series.values.astype(float)

    # Simple linear regression
    x_mean = x.mean()
    y_mean = y.mean()
    numerator = ((x - x_mean) * (y - y_mean)).sum()
    denominator = ((x - x_mean) ** 2).sum()

    if denominator == 0:
        return None

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    # Calculate residual standard deviation
    predicted = slope * x + intercept
    residuals = y - predicted
    std_dev = np.std(residuals) if len(residuals) > 0 else 0.0

    return PredictionModel(
        metric=series.name if hasattr(series, "name") else "unknown",
        method="linear",
        slope=float(slope),
        intercept=float(intercept),
        std_dev=float(std_dev),
        last_values=list(y[-7:]) if len(y) >= 7 else list(y),
    )


def fit_moving_average(
    series: pd.Series, window: int = 7, min_points: int = 7
) -> Optional[PredictionModel]:
    """Fit a moving average model.

    Args:
        series: Time series with datetime index
        window: Window size for moving average
        min_points: Minimum data points required

    Returns:
        PredictionModel or None if insufficient data
    """
    series = series.dropna()
    if len(series) < min_points:
        return None

    values = series.values.astype(float)
    last_values = list(values[-window:]) if len(values) >= window else list(values)

    # Calculate standard deviation of recent values
    std_dev = float(np.std(last_values)) if len(last_values) > 1 else 0.0

    return PredictionModel(
        metric=series.name if hasattr(series, "name") else "unknown",
        method="moving_avg",
        window_size=window,
        last_values=last_values,
        std_dev=std_dev,
    )


def predict_next_days(
    model: PredictionModel, days: int = 7
) -> List[Forecast]:
    """Generate forecasts for the next N days.

    Args:
        model: Trained prediction model
        days: Number of days to forecast

    Returns:
        List of Forecast objects
    """
    forecasts = []
    today = date.today()

    for i in range(1, days + 1):
        forecast_date = today + timedelta(days=i)

        if model.method == "linear" and model.slope is not None:
            # Linear extrapolation
            n_historical = len(model.last_values)
            x = n_historical + i - 1
            predicted = model.slope * x + model.intercept
            confidence = max(0.3, 1.0 - (i * 0.1))  # Decreases with distance

            lower = predicted - 2 * model.std_dev
            upper = predicted + 2 * model.std_dev

        elif model.method == "moving_avg":
            # Moving average stays flat
            predicted = np.mean(model.last_values)
            confidence = max(0.4, 1.0 - (i * 0.08))

            lower = predicted - 2 * model.std_dev
            upper = predicted + 2 * model.std_dev

        else:
            continue

        forecasts.append(
            Forecast(
                metric=model.metric,
                date=forecast_date,
                predicted_value=float(predicted),
                confidence=confidence,
                method=model.method,
                lower_bound=float(lower),
                upper_bound=float(upper),
            )
        )

    return forecasts


def predict_conditional(
    df: pd.DataFrame,
    cause_metric: str,
    effect_metric: str,
    cause_value: float,
    lag_days: int = 1,
    min_points: int = 14,
) -> Optional[ConditionalPrediction]:
    """Predict effect metric based on cause metric value.

    "If your sleep is X hours, expect your energy to be Y tomorrow."

    Args:
        df: DataFrame with metrics as columns
        cause_metric: The predictor metric
        effect_metric: The metric to predict
        cause_value: The current value of cause metric
        lag_days: How many days the effect is delayed
        min_points: Minimum data points required

    Returns:
        ConditionalPrediction or None
    """
    if cause_metric not in df.columns or effect_metric not in df.columns:
        return None

    cause = df[cause_metric].dropna()
    effect = df[effect_metric].dropna()

    if len(cause) < min_points or len(effect) < min_points:
        return None

    # Align with lag
    if lag_days > 0:
        effect_lagged = effect.shift(-lag_days)
    else:
        effect_lagged = effect

    # Find common indices
    common = cause.index.intersection(effect_lagged.dropna().index)
    if len(common) < min_points:
        return None

    x = cause[common].values.astype(float)
    y = effect_lagged[common].values.astype(float)

    # Calculate correlation
    correlation = np.corrcoef(x, y)[0, 1]
    if np.isnan(correlation):
        return None

    # Determine relationship
    if correlation > 0.3:
        relationship = "positive"
    elif correlation < -0.3:
        relationship = "negative"
    else:
        relationship = "none"

    # Simple linear regression to predict
    x_mean, y_mean = x.mean(), y.mean()
    numerator = ((x - x_mean) * (y - y_mean)).sum()
    denominator = ((x - x_mean) ** 2).sum()

    if denominator == 0:
        return None

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    predicted_effect = slope * cause_value + intercept
    confidence = abs(correlation)

    # Generate insight
    if relationship == "positive":
        direction = "higher" if cause_value > x_mean else "lower"
        effect_direction = "higher" if predicted_effect > y_mean else "lower"
        insight = f"With {cause_metric} at {cause_value:.1f}, expect {effect_metric} to be {effect_direction} than average ({predicted_effect:.1f} vs {y_mean:.1f})"
    elif relationship == "negative":
        direction = "higher" if cause_value > x_mean else "lower"
        effect_direction = "lower" if cause_value > x_mean else "higher"
        insight = f"With {cause_metric} {direction} than usual, {effect_metric} tends to be {effect_direction}"
    else:
        insight = f"No strong relationship between {cause_metric} and {effect_metric}"

    return ConditionalPrediction(
        cause_metric=cause_metric,
        effect_metric=effect_metric,
        cause_value=cause_value,
        expected_effect=float(predicted_effect),
        confidence=confidence,
        lag_days=lag_days,
        relationship=relationship,
        insight=insight,
    )


def find_predictive_relationships(
    df: pd.DataFrame,
    target_metric: str,
    candidate_metrics: Optional[List[str]] = None,
    max_lag: int = 3,
    min_correlation: float = 0.3,
    min_points: int = 14,
) -> List[Tuple[str, int, float]]:
    """Find metrics that predict the target metric.

    Returns list of (metric, lag_days, correlation) tuples.
    """
    if target_metric not in df.columns:
        return []

    target = df[target_metric].dropna()
    if len(target) < min_points:
        return []

    candidates = candidate_metrics or [c for c in df.columns if c != target_metric]
    results = []

    for metric in candidates:
        if metric not in df.columns:
            continue

        series = df[metric].dropna()
        if len(series) < min_points:
            continue

        for lag in range(max_lag + 1):
            if lag > 0:
                target_lagged = target.shift(-lag)
            else:
                target_lagged = target

            common = series.index.intersection(target_lagged.dropna().index)
            if len(common) < min_points:
                continue

            x = series[common].values.astype(float)
            y = target_lagged[common].values.astype(float)

            correlation = np.corrcoef(x, y)[0, 1]
            if np.isnan(correlation):
                continue

            if abs(correlation) >= min_correlation:
                results.append((metric, lag, float(correlation)))

    # Sort by absolute correlation
    results.sort(key=lambda r: abs(r[2]), reverse=True)
    return results


def format_forecast(forecasts: List[Forecast]) -> str:
    """Format forecasts as readable text."""
    if not forecasts:
        return "No forecasts available."

    lines = [f"Forecast for {forecasts[0].metric}:"]
    lines.append("-" * 40)

    for f in forecasts:
        bounds = ""
        if f.lower_bound is not None and f.upper_bound is not None:
            bounds = f" [{f.lower_bound:.1f} - {f.upper_bound:.1f}]"

        conf_pct = int(f.confidence * 100)
        lines.append(
            f"  {f.date}: {f.predicted_value:.1f}{bounds} ({conf_pct}% conf)"
        )

    return "\n".join(lines)


def format_conditional(pred: ConditionalPrediction) -> str:
    """Format conditional prediction as readable text."""
    return f"""
If {pred.cause_metric} = {pred.cause_value:.1f}:
  Expected {pred.effect_metric}: {pred.expected_effect:.1f}
  (Lag: {pred.lag_days} day(s), Confidence: {int(pred.confidence * 100)}%)
  
{pred.insight}
""".strip()
