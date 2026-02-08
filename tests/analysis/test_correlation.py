"""Tests for correlation analysis."""

import numpy as np
import pandas as pd
import pytest

from resonance.analysis.correlation import (
    CorrelationResult,
    apply_bonferroni,
    calculate_confidence,
    calculate_correlation,
    find_all_correlations,
)


@pytest.fixture
def sample_df():
    """Create a sample DataFrame with correlated metrics."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60)
    base = np.random.randn(60).cumsum()

    return pd.DataFrame(
        {
            "steps": base * 1000 + 5000,
            "mood": base * 0.3 + 5 + np.random.randn(60) * 0.5,
            "sleep": np.random.randn(60) * 1.5 + 7,  # Uncorrelated
            "energy": base * 0.4 + 6 + np.random.randn(60) * 0.3,
        },
        index=dates,
    )


class TestCalculateCorrelation:
    def test_positive_correlation(self, sample_df):
        """Positively correlated metrics should have r > 0."""
        result = calculate_correlation(sample_df, "steps", "mood")
        assert result is not None
        assert result.correlation > 0.3
        assert result.p_value < 0.05
        assert result.sample_size == 60

    def test_negative_correlation(self):
        """Negative correlation should have r < 0."""
        dates = pd.date_range("2024-01-01", periods=30)
        df = pd.DataFrame(
            {"a": range(30), "b": range(29, -1, -1)}, index=dates  # Perfect negative
        )
        result = calculate_correlation(df, "a", "b")
        assert result is not None
        assert result.correlation < -0.9

    def test_near_zero_correlation(self, sample_df):
        """Uncorrelated metrics should have r near 0."""
        result = calculate_correlation(sample_df, "steps", "sleep")
        # Sleep is random, so correlation should be weak
        assert result is not None
        assert abs(result.correlation) < 0.5

    def test_insufficient_data_returns_none(self):
        """Less than 14 days should return None."""
        dates = pd.date_range("2024-01-01", periods=10)
        df = pd.DataFrame({"a": range(10), "b": range(10)}, index=dates)
        result = calculate_correlation(df, "a", "b")
        assert result is None

    def test_no_overlap_returns_none(self):
        """Non-overlapping data should return None."""
        dates = pd.date_range("2024-01-01", periods=30)
        df = pd.DataFrame(
            {
                "a": list(range(15)) + [np.nan] * 15,
                "b": [np.nan] * 15 + list(range(15)),
            },
            index=dates,
        )
        result = calculate_correlation(df, "a", "b")
        assert result is None

    def test_lagged_correlation_lag1(self):
        """Lagged correlation should detect delayed effects."""
        dates = pd.date_range("2024-01-01", periods=30)
        base = np.arange(30)
        df = pd.DataFrame(
            {
                "cause": base,
                "effect": np.concatenate([[0], base[:-1]]),  # Shifted by 1
            },
            index=dates,
        )
        result = calculate_correlation(df, "cause", "effect", lag=1)
        assert result is not None
        assert result.correlation > 0.9
        assert result.lag_days == 1

    def test_lagged_correlation_lag2(self):
        """Lag of 2 should detect two-day delayed effects."""
        dates = pd.date_range("2024-01-01", periods=30)
        base = np.arange(30)
        df = pd.DataFrame(
            {
                "cause": base,
                "effect": np.concatenate([[0, 0], base[:-2]]),  # Shifted by 2
            },
            index=dates,
        )
        result = calculate_correlation(df, "cause", "effect", lag=2)
        assert result is not None
        assert result.correlation > 0.9
        assert result.lag_days == 2

    def test_missing_metric_returns_none(self, sample_df):
        """Non-existent metric should return None."""
        result = calculate_correlation(sample_df, "steps", "nonexistent")
        assert result is None


class TestCalculateConfidence:
    def test_high_confidence(self):
        """High confidence: n>=50, p<0.01, |r|>=0.5."""
        assert calculate_confidence(0.6, 0.005, 50) == "high"
        assert calculate_confidence(-0.7, 0.001, 100) == "high"

    def test_medium_confidence(self):
        """Medium confidence: n>=30, p<0.05, |r|>=0.3."""
        assert calculate_confidence(0.4, 0.03, 35) == "medium"
        assert calculate_confidence(-0.35, 0.04, 30) == "medium"

    def test_low_confidence(self):
        """Low confidence: n>=14, p<0.05, |r|>=0.3."""
        assert calculate_confidence(0.35, 0.04, 15) == "low"
        assert calculate_confidence(-0.32, 0.03, 20) == "low"

    def test_none_confidence(self):
        """No confidence when thresholds not met."""
        assert calculate_confidence(0.2, 0.04, 50) == "none"  # r too low
        assert calculate_confidence(0.5, 0.1, 50) == "none"  # p too high
        assert calculate_confidence(0.5, 0.01, 10) == "none"  # n too low


class TestFindAllCorrelations:
    def test_find_correlations(self, sample_df):
        """Should find correlations between related metrics."""
        results = find_all_correlations(sample_df, max_lag=0)
        assert len(results) > 0
        # steps and mood should be correlated
        pairs = [(r.metric1, r.metric2) for r in results]
        has_steps_mood = any(
            ("steps" in p and "mood" in p) or ("mood" in p and "steps" in p)
            for p in pairs
        )
        assert has_steps_mood

    def test_filter_by_min_correlation(self, sample_df):
        """Should filter out weak correlations."""
        results = find_all_correlations(sample_df, min_correlation=0.8)
        for r in results:
            assert abs(r.correlation) >= 0.8

    def test_filter_by_p_threshold(self, sample_df):
        """Should filter out non-significant correlations."""
        results = find_all_correlations(sample_df, p_threshold=0.01)
        for r in results:
            assert r.p_value < 0.01

    def test_handle_missing_values(self):
        """Should handle NaN values properly."""
        dates = pd.date_range("2024-01-01", periods=30)
        df = pd.DataFrame(
            {
                "a": list(range(15)) + [np.nan] * 5 + list(range(10)),
                "b": list(range(30)),
            },
            index=dates,
        )
        results = find_all_correlations(df)
        # Should work, just with fewer samples
        assert isinstance(results, list)


class TestApplyBonferroni:
    def test_bonferroni_filters_weak(self):
        """Should filter results that don't pass corrected threshold."""
        results = [
            CorrelationResult("a", "b", 0.5, 0.004, 50, 0, "high"),  # Passes: 0.004*10=0.04 < 0.05
            CorrelationResult("c", "d", 0.4, 0.02, 40, 0, "medium"),  # Fails: 0.02*10=0.2 >= 0.05
        ]
        filtered = apply_bonferroni(results, num_tests=10)
        assert len(filtered) == 1
        assert filtered[0].metric1 == "a"

    def test_bonferroni_zero_tests(self):
        """Zero tests should return all results."""
        results = [CorrelationResult("a", "b", 0.5, 0.01, 50, 0, "high")]
        filtered = apply_bonferroni(results, num_tests=0)
        assert len(filtered) == 1
