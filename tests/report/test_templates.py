"""Tests for natural language templates."""


from resonance.analysis.correlation import CorrelationResult
from resonance.analysis.patterns import WeekdayPattern
from resonance.analysis.trends import TrendResult
from resonance.report.templates import (
    describe_correlation,
    describe_data_quality,
    describe_trend,
    describe_weekday_pattern,
    generate_insight_summary,
)


class TestDescribeCorrelation:
    def test_positive_correlation(self):
        """Should describe positive correlation."""
        r = CorrelationResult("steps", "mood", 0.65, 0.001, 50, 0, "high")
        desc = describe_correlation(r)
        assert "steps" in desc
        assert "mood" in desc
        assert "higher" in desc
        assert "0.65" in desc

    def test_negative_correlation(self):
        """Should describe negative correlation."""
        r = CorrelationResult("stress", "sleep", -0.55, 0.001, 50, 0, "high")
        desc = describe_correlation(r)
        assert "lower" in desc
        assert "-0.55" in desc

    def test_strong_correlation(self):
        """Should describe strong correlation."""
        r = CorrelationResult("a", "b", 0.8, 0.001, 50, 0, "high")
        desc = describe_correlation(r)
        assert "strongly" in desc

    def test_lagged_correlation(self):
        """Should describe lagged correlation."""
        r = CorrelationResult("exercise", "mood", 0.45, 0.01, 40, 1, "medium")
        desc = describe_correlation(r)
        assert "1 day" in desc
        assert "predicts" in desc


class TestDescribeWeekdayPattern:
    def test_weekday_higher(self):
        """Should describe higher weekday."""
        p = WeekdayPattern("steps", 0, "Monday", 8000, 6000, 33.3, True)
        desc = describe_weekday_pattern(p)
        assert "Monday" in desc
        assert "higher" in desc
        assert "33%" in desc

    def test_weekday_lower(self):
        """Should describe lower weekday."""
        p = WeekdayPattern("steps", 6, "Sunday", 4000, 6000, -33.3, True)
        desc = describe_weekday_pattern(p)
        assert "Sunday" in desc
        assert "lower" in desc


class TestDescribeTrend:
    def test_trend_up(self):
        """Should describe upward trend."""
        t = TrendResult("steps", 5000, 6000, 20.0, "up")
        desc = describe_trend(t)
        assert "increased" in desc
        assert "20%" in desc

    def test_trend_down(self):
        """Should describe downward trend."""
        t = TrendResult("mood", 7.0, 5.0, -28.6, "down")
        desc = describe_trend(t)
        assert "decreased" in desc
        assert "29%" in desc  # Rounded

    def test_trend_stable(self):
        """Should describe stable trend."""
        t = TrendResult("sleep", 7.0, 7.1, 1.4, "stable")
        desc = describe_trend(t)
        assert "stable" in desc


class TestDescribeDataQuality:
    def test_data_quality(self):
        """Should describe data quality."""
        quality = {"steps": (55, 60), "mood": (60, 60)}
        desc = describe_data_quality(quality)
        assert "steps" in desc
        assert "55/60" in desc
        assert "92%" in desc  # 55/60 = 91.6% rounds to 92%
        assert "mood" in desc
        assert "100%" in desc

    def test_empty_quality(self):
        """Should handle empty quality dict."""
        desc = describe_data_quality({})
        assert "No data quality" in desc

    def test_zero_total_days(self):
        """Should handle zero total days."""
        quality = {"steps": (0, 0)}
        desc = describe_data_quality(quality)
        assert "no data" in desc


class TestGenerateInsightSummary:
    def test_full_summary(self):
        """Should generate full summary."""
        patterns = [CorrelationResult("steps", "mood", 0.65, 0.001, 50, 0, "high")]
        weekday_effects = [
            WeekdayPattern("steps", 0, "Monday", 8000, 6000, 33.3, True)
        ]
        trends = [TrendResult("steps", 5000, 6000, 20.0, "up")]

        summary = generate_insight_summary(patterns, weekday_effects, trends)
        assert "steps" in summary
        assert "mood" in summary
        assert "Monday" in summary
        assert "increased" in summary

    def test_empty_summary(self):
        """Should handle no insights."""
        summary = generate_insight_summary([], [], [])
        assert "No significant patterns" in summary
