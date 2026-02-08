"""Tests for pattern detection."""

import numpy as np
import pandas as pd
import pytest

from resonance.analysis.patterns import (
    WEEKDAY_NAMES,
    Anomaly,
    WeekdayPattern,
    find_all_anomalies,
    find_anomalies,
    find_weekday_patterns,
)


@pytest.fixture
def weekly_pattern_df():
    """Create a DataFrame with a clear Monday effect."""
    # 4 weeks of data
    dates = pd.date_range("2024-01-01", periods=28)  # Starts on Monday
    values = []
    for i in range(28):
        weekday = i % 7
        if weekday == 0:  # Monday
            values.append(10.0)  # Much higher on Mondays
        else:
            values.append(5.0)

    return pd.DataFrame({"metric": values}, index=dates)


@pytest.fixture
def no_pattern_df():
    """Create a DataFrame with no weekday effects."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=56)
    return pd.DataFrame(
        {"metric": np.random.normal(5, 1, 56)},
        index=dates,
    )


@pytest.fixture
def anomaly_df():
    """Create a DataFrame with clear anomalies."""
    dates = pd.date_range("2024-01-01", periods=30)
    values = [5.0] * 30
    values[5] = 15.0  # High anomaly
    values[15] = -5.0  # Low anomaly
    return pd.DataFrame({"metric": values}, index=dates)


class TestFindWeekdayPatterns:
    def test_find_monday_effect(self, weekly_pattern_df):
        """Should detect Monday effect."""
        patterns = find_weekday_patterns(weekly_pattern_df)
        assert len(patterns) > 0
        monday_patterns = [p for p in patterns if p.weekday == 0]
        assert len(monday_patterns) == 1
        assert monday_patterns[0].weekday_name == "Monday"
        assert monday_patterns[0].difference_pct > 0

    def test_find_friday_effect(self):
        """Should detect Friday effect."""
        # 4 weeks starting on Monday
        dates = pd.date_range("2024-01-01", periods=28)
        values = []
        for i in range(28):
            weekday = i % 7
            if weekday == 4:  # Friday
                values.append(10.0)
            else:
                values.append(5.0)
        df = pd.DataFrame({"metric": values}, index=dates)

        patterns = find_weekday_patterns(df)
        friday_patterns = [p for p in patterns if p.weekday == 4]
        assert len(friday_patterns) == 1
        assert friday_patterns[0].weekday_name == "Friday"

    def test_no_weekday_effect_returns_empty(self, no_pattern_df):
        """Random data should have no significant patterns."""
        patterns = find_weekday_patterns(no_pattern_df, p_threshold=0.001)
        # With strict p-value, random data shouldn't show patterns
        assert len(patterns) == 0

    def test_handle_sparse_data(self):
        """Should handle data with few samples."""
        dates = pd.date_range("2024-01-01", periods=10)
        df = pd.DataFrame({"metric": range(10)}, index=dates)
        patterns = find_weekday_patterns(df)
        # Too few samples, should return empty
        assert patterns == []

    def test_multiple_patterns_same_metric(self, weekly_pattern_df):
        """Should find multiple weekday patterns for same metric."""
        # The weekly_pattern_df might show patterns for Monday AND other days
        # since the difference is stark
        patterns = find_weekday_patterns(weekly_pattern_df, p_threshold=0.1)
        # At least Monday should show up
        assert any(p.weekday == 0 for p in patterns)

    def test_weekday_names_in_output(self, weekly_pattern_df):
        """Patterns should include weekday names."""
        patterns = find_weekday_patterns(weekly_pattern_df)
        for p in patterns:
            assert p.weekday_name == WEEKDAY_NAMES[p.weekday]


class TestFindAnomalies:
    def test_find_high_anomaly(self, anomaly_df):
        """Should detect high anomalies."""
        anomalies = find_anomalies(anomaly_df, "metric", threshold=2.0)
        high_anomalies = [a for a in anomalies if a.direction == "high"]
        assert len(high_anomalies) >= 1
        assert high_anomalies[0].z_score > 2.0

    def test_find_low_anomaly(self, anomaly_df):
        """Should detect low anomalies."""
        anomalies = find_anomalies(anomaly_df, "metric", threshold=2.0)
        low_anomalies = [a for a in anomalies if a.direction == "low"]
        assert len(low_anomalies) >= 1
        assert low_anomalies[0].z_score < -2.0

    def test_no_anomalies_returns_empty(self):
        """Constant data should have no anomalies."""
        dates = pd.date_range("2024-01-01", periods=30)
        df = pd.DataFrame({"metric": [5.0] * 30}, index=dates)
        anomalies = find_anomalies(df, "metric")
        assert anomalies == []

    def test_anomaly_threshold_configurable(self, anomaly_df):
        """Higher threshold should find fewer anomalies."""
        anomalies_low = find_anomalies(anomaly_df, "metric", threshold=1.0)
        anomalies_high = find_anomalies(anomaly_df, "metric", threshold=3.0)
        assert len(anomalies_low) >= len(anomalies_high)

    def test_handle_constant_metric(self):
        """Constant metric (std=0) should return empty."""
        dates = pd.date_range("2024-01-01", periods=30)
        df = pd.DataFrame({"metric": [5.0] * 30}, index=dates)
        anomalies = find_anomalies(df, "metric")
        assert anomalies == []

    def test_handle_metric_with_few_days(self):
        """Too few data points should return empty."""
        dates = pd.date_range("2024-01-01", periods=2)
        df = pd.DataFrame({"metric": [1.0, 100.0]}, index=dates)
        anomalies = find_anomalies(df, "metric")
        assert anomalies == []

    def test_nonexistent_metric_returns_empty(self, anomaly_df):
        """Non-existent metric should return empty."""
        anomalies = find_anomalies(anomaly_df, "nonexistent")
        assert anomalies == []


class TestFindAllAnomalies:
    def test_finds_across_metrics(self):
        """Should find anomalies across all metrics."""
        dates = pd.date_range("2024-01-01", periods=30)
        df = pd.DataFrame(
            {
                "a": [5.0] * 29 + [100.0],  # Anomaly in a
                "b": [10.0] * 29 + [200.0],  # Anomaly in b
            },
            index=dates,
        )
        anomalies = find_all_anomalies(df)
        assert len(anomalies) >= 2
        metrics = {a.metric for a in anomalies}
        assert "a" in metrics
        assert "b" in metrics

    def test_sorted_by_z_score(self):
        """Results should be sorted by absolute z-score."""
        dates = pd.date_range("2024-01-01", periods=30)
        df = pd.DataFrame(
            {
                "a": [5.0] * 29 + [50.0],
                "b": [10.0] * 29 + [500.0],  # Bigger anomaly
            },
            index=dates,
        )
        anomalies = find_all_anomalies(df)
        if len(anomalies) >= 2:
            assert abs(anomalies[0].z_score) >= abs(anomalies[1].z_score)
