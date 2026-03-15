"""Tests for prediction module."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from resonance.analysis.prediction import (
    ConditionalPrediction,
    Forecast,
    PredictionModel,
    fit_linear_trend,
    fit_moving_average,
    find_predictive_relationships,
    format_conditional,
    format_forecast,
    predict_conditional,
    predict_next_days,
)


@pytest.fixture
def linear_series():
    """Create a series with linear trend."""
    dates = pd.date_range(start="2026-01-01", periods=30, freq="D")
    values = [50 + i * 0.5 + np.random.normal(0, 1) for i in range(30)]
    return pd.Series(values, index=dates, name="metric")


@pytest.fixture
def flat_series():
    """Create a flat series."""
    dates = pd.date_range(start="2026-01-01", periods=30, freq="D")
    values = [50 + np.random.normal(0, 2) for _ in range(30)]
    return pd.Series(values, index=dates, name="metric")


@pytest.fixture
def correlated_df():
    """Create DataFrame with correlated metrics."""
    dates = pd.date_range(start="2026-01-01", periods=30, freq="D")
    # Sleep affects energy the next day (positive correlation)
    sleep = [7 + np.random.normal(0, 0.5) for _ in range(30)]
    energy = [0] + [sleep[i-1] * 10 + np.random.normal(0, 5) for i in range(1, 30)]
    # Stress is negatively correlated with mood
    stress = [5 + np.random.normal(0, 1) for _ in range(30)]
    mood = [10 - s * 0.5 + np.random.normal(0, 1) for s in stress]
    
    return pd.DataFrame({
        "sleep": sleep,
        "energy": energy,
        "stress": stress,
        "mood": mood,
    }, index=dates)


class TestFitLinearTrend:
    def test_fit_linear_trend_basic(self, linear_series):
        model = fit_linear_trend(linear_series)
        assert model is not None
        assert model.method == "linear"
        assert model.slope is not None
        assert model.slope > 0  # Upward trend

    def test_fit_linear_trend_insufficient_data(self):
        series = pd.Series([1, 2, 3], name="test")
        model = fit_linear_trend(series, min_points=7)
        assert model is None

    def test_fit_linear_trend_calculates_std(self, linear_series):
        model = fit_linear_trend(linear_series)
        assert model.std_dev >= 0

    def test_fit_linear_trend_stores_last_values(self, linear_series):
        model = fit_linear_trend(linear_series)
        assert len(model.last_values) == 7


class TestFitMovingAverage:
    def test_fit_moving_average_basic(self, flat_series):
        model = fit_moving_average(flat_series)
        assert model is not None
        assert model.method == "moving_avg"
        assert model.window_size == 7

    def test_fit_moving_average_custom_window(self, flat_series):
        model = fit_moving_average(flat_series, window=14)
        assert model.window_size == 14

    def test_fit_moving_average_insufficient_data(self):
        series = pd.Series([1, 2, 3])
        model = fit_moving_average(series, min_points=7)
        assert model is None


class TestPredictNextDays:
    def test_predict_linear(self, linear_series):
        model = fit_linear_trend(linear_series)
        forecasts = predict_next_days(model, days=7)
        
        assert len(forecasts) == 7
        assert all(isinstance(f, Forecast) for f in forecasts)
        assert all(f.method == "linear" for f in forecasts)

    def test_predict_moving_avg(self, flat_series):
        model = fit_moving_average(flat_series)
        forecasts = predict_next_days(model, days=7)
        
        assert len(forecasts) == 7
        assert all(f.method == "moving_avg" for f in forecasts)

    def test_forecast_has_bounds(self, linear_series):
        model = fit_linear_trend(linear_series)
        forecasts = predict_next_days(model, days=3)
        
        for f in forecasts:
            assert f.lower_bound is not None
            assert f.upper_bound is not None
            assert f.lower_bound < f.predicted_value < f.upper_bound

    def test_confidence_decreases_with_distance(self, linear_series):
        model = fit_linear_trend(linear_series)
        forecasts = predict_next_days(model, days=7)
        
        confidences = [f.confidence for f in forecasts]
        assert confidences[0] > confidences[-1]

    def test_forecast_dates_are_future(self, linear_series):
        model = fit_linear_trend(linear_series)
        forecasts = predict_next_days(model, days=3)
        
        today = date.today()
        for f in forecasts:
            assert f.date > today


class TestPredictConditional:
    def test_predict_conditional_positive(self, correlated_df):
        pred = predict_conditional(
            correlated_df,
            cause_metric="sleep",
            effect_metric="energy",
            cause_value=8.0,
            lag_days=1,
        )
        
        assert pred is not None
        assert pred.relationship == "positive"
        assert pred.confidence > 0.3

    def test_predict_conditional_negative(self, correlated_df):
        pred = predict_conditional(
            correlated_df,
            cause_metric="stress",
            effect_metric="mood",
            cause_value=7.0,
            lag_days=0,
        )
        
        assert pred is not None
        assert pred.relationship == "negative"

    def test_predict_conditional_generates_insight(self, correlated_df):
        pred = predict_conditional(
            correlated_df,
            cause_metric="sleep",
            effect_metric="energy",
            cause_value=8.0,
            lag_days=1,
        )
        
        assert pred.insight
        assert len(pred.insight) > 10

    def test_predict_conditional_missing_metric(self, correlated_df):
        pred = predict_conditional(
            correlated_df,
            cause_metric="nonexistent",
            effect_metric="energy",
            cause_value=8.0,
        )
        assert pred is None

    def test_predict_conditional_insufficient_data(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        pred = predict_conditional(df, "a", "b", 2.0, min_points=14)
        assert pred is None


class TestFindPredictiveRelationships:
    def test_find_relationships(self, correlated_df):
        results = find_predictive_relationships(
            correlated_df,
            target_metric="energy",
            max_lag=2,
            min_correlation=0.3,
        )
        
        assert len(results) > 0
        assert all(len(r) == 3 for r in results)  # (metric, lag, correlation)

    def test_find_relationships_sorted_by_correlation(self, correlated_df):
        results = find_predictive_relationships(
            correlated_df,
            target_metric="energy",
            min_correlation=0.1,
        )
        
        if len(results) >= 2:
            # Should be sorted by absolute correlation, descending
            assert abs(results[0][2]) >= abs(results[1][2])

    def test_find_relationships_missing_target(self, correlated_df):
        results = find_predictive_relationships(
            correlated_df,
            target_metric="nonexistent",
        )
        assert results == []


class TestFormatFunctions:
    def test_format_forecast_empty(self):
        result = format_forecast([])
        assert "No forecasts" in result

    def test_format_forecast_with_data(self, linear_series):
        model = fit_linear_trend(linear_series)
        forecasts = predict_next_days(model, days=3)
        result = format_forecast(forecasts)
        
        assert "Forecast" in result
        assert "metric" in result

    def test_format_conditional(self, correlated_df):
        pred = predict_conditional(
            correlated_df,
            cause_metric="sleep",
            effect_metric="energy",
            cause_value=8.0,
            lag_days=1,
        )
        
        result = format_conditional(pred)
        assert "sleep" in result
        assert "energy" in result
        assert "8.0" in result


class TestEdgeCases:
    def test_constant_series(self):
        """Series with no variance."""
        series = pd.Series([50.0] * 20, name="constant")
        model = fit_linear_trend(series)
        assert model is not None
        assert abs(model.slope) < 0.01  # Near-zero slope

    def test_series_with_nans(self):
        """Series with missing values."""
        dates = pd.date_range(start="2026-01-01", periods=20)
        values = [float(i) if i % 3 != 0 else np.nan for i in range(20)]
        series = pd.Series(values, index=dates, name="with_nans")
        
        model = fit_linear_trend(series)
        # Should still work with enough non-nan values
        assert model is not None

    def test_prediction_model_defaults(self):
        """Test PredictionModel default values."""
        model = PredictionModel(metric="test", method="linear")
        assert model.slope is None
        assert model.last_values == []
        assert model.std_dev == 0.0
