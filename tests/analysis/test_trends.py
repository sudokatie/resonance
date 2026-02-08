"""Tests for trend analysis."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from resonance.analysis.trends import (
    compare_periods,
    find_all_trends,
    month_over_month,
    week_over_week,
)


@pytest.fixture
def trend_df():
    """Create a DataFrame with clear trends."""
    dates = pd.date_range("2024-01-01", periods=60)
    # Increasing trend
    values = np.arange(60) * 0.5 + 10
    return pd.DataFrame({"metric": values}, index=dates)


class TestComparePeriods:
    def test_compare_periods_increase(self):
        """Should detect increase between periods."""
        dates = pd.date_range("2024-01-01", periods=20)
        df = pd.DataFrame(
            {"metric": [5.0] * 10 + [10.0] * 10},
            index=dates,
        )
        result = compare_periods(
            df,
            "metric",
            ("2024-01-01", "2024-01-10"),
            ("2024-01-11", "2024-01-20"),
        )
        assert result is not None
        assert result.direction == "up"
        assert result.change_pct == pytest.approx(100.0, rel=0.1)

    def test_compare_periods_decrease(self):
        """Should detect decrease between periods."""
        dates = pd.date_range("2024-01-01", periods=20)
        df = pd.DataFrame(
            {"metric": [10.0] * 10 + [5.0] * 10},
            index=dates,
        )
        result = compare_periods(
            df,
            "metric",
            ("2024-01-01", "2024-01-10"),
            ("2024-01-11", "2024-01-20"),
        )
        assert result is not None
        assert result.direction == "down"
        assert result.change_pct == pytest.approx(-50.0, rel=0.1)

    def test_compare_periods_stable(self):
        """Should detect stable when change is small."""
        dates = pd.date_range("2024-01-01", periods=20)
        df = pd.DataFrame(
            {"metric": [10.0] * 10 + [10.3] * 10},  # 3% increase
            index=dates,
        )
        result = compare_periods(
            df,
            "metric",
            ("2024-01-01", "2024-01-10"),
            ("2024-01-11", "2024-01-20"),
        )
        assert result is not None
        assert result.direction == "stable"

    def test_handle_missing_data_in_period(self):
        """Should handle NaN values in periods."""
        dates = pd.date_range("2024-01-01", periods=20)
        values = [5.0] * 10 + [10.0] * 10
        values[5] = np.nan  # Add a NaN
        df = pd.DataFrame({"metric": values}, index=dates)
        result = compare_periods(
            df,
            "metric",
            ("2024-01-01", "2024-01-10"),
            ("2024-01-11", "2024-01-20"),
        )
        assert result is not None

    def test_handle_single_day_period(self):
        """Single day period should return None (< 3 days)."""
        dates = pd.date_range("2024-01-01", periods=10)
        df = pd.DataFrame({"metric": range(10)}, index=dates)
        result = compare_periods(
            df,
            "metric",
            ("2024-01-01", "2024-01-01"),
            ("2024-01-10", "2024-01-10"),
        )
        assert result is None

    def test_handle_zero_baseline(self):
        """Should handle zero baseline (m1=0)."""
        dates = pd.date_range("2024-01-01", periods=20)
        df = pd.DataFrame(
            {"metric": [0.0] * 10 + [10.0] * 10},
            index=dates,
        )
        result = compare_periods(
            df,
            "metric",
            ("2024-01-01", "2024-01-10"),
            ("2024-01-11", "2024-01-20"),
        )
        assert result is not None
        assert result.direction == "up"

    def test_direction_threshold(self):
        """5% threshold should separate stable from up/down."""
        dates = pd.date_range("2024-01-01", periods=20)

        # 4% increase - should be stable
        df1 = pd.DataFrame(
            {"metric": [10.0] * 10 + [10.4] * 10},
            index=dates,
        )
        r1 = compare_periods(
            df1, "metric", ("2024-01-01", "2024-01-10"), ("2024-01-11", "2024-01-20")
        )
        assert r1.direction == "stable"

        # 6% increase - should be up
        df2 = pd.DataFrame(
            {"metric": [10.0] * 10 + [10.6] * 10},
            index=dates,
        )
        r2 = compare_periods(
            df2, "metric", ("2024-01-01", "2024-01-10"), ("2024-01-11", "2024-01-20")
        )
        assert r2.direction == "up"

    def test_nonexistent_metric(self, trend_df):
        """Non-existent metric should return None."""
        result = compare_periods(
            trend_df,
            "nonexistent",
            ("2024-01-01", "2024-01-10"),
            ("2024-01-11", "2024-01-20"),
        )
        assert result is None


class TestWeekOverWeek:
    def test_week_over_week_up(self):
        """Should detect weekly increase."""
        # Use a reference date
        ref = date(2024, 1, 21)  # Sunday of week 3
        dates = pd.date_range("2024-01-01", periods=21)
        # Week 2 (Jan 8-14): values ~5, Week 3 (Jan 15-21): values ~10
        values = [3.0] * 7 + [5.0] * 7 + [10.0] * 7
        df = pd.DataFrame({"metric": values}, index=dates)

        result = week_over_week(df, "metric", reference_date=ref)
        assert result is not None
        assert result.direction == "up"

    def test_week_over_week_down(self):
        """Should detect weekly decrease."""
        ref = date(2024, 1, 21)
        dates = pd.date_range("2024-01-01", periods=21)
        values = [3.0] * 7 + [10.0] * 7 + [5.0] * 7
        df = pd.DataFrame({"metric": values}, index=dates)

        result = week_over_week(df, "metric", reference_date=ref)
        assert result is not None
        assert result.direction == "down"


class TestMonthOverMonth:
    def test_month_over_month(self):
        """Should compare months correctly."""
        ref = date(2024, 2, 15)
        dates = pd.date_range("2024-01-01", periods=46)  # Jan 1 - Feb 15
        values = [5.0] * 31 + [10.0] * 15  # Jan: 5, Feb: 10
        df = pd.DataFrame({"metric": values}, index=dates)

        result = month_over_month(df, "metric", reference_date=ref)
        assert result is not None
        assert result.direction == "up"
        assert result.change_pct == pytest.approx(100.0, rel=0.1)


class TestFindAllTrends:
    def test_finds_trends_for_all_metrics(self, trend_df):
        """Should find trends for all metrics."""
        # Add another metric
        trend_df["other"] = trend_df["metric"] * 2
        ref = date(2024, 2, 15)

        trends = find_all_trends(trend_df, reference_date=ref)
        assert "weekly" in trends
        assert "monthly" in trends
