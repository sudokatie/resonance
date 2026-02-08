"""Tests for report generation."""

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from resonance.analysis.correlation import CorrelationResult
from resonance.analysis.patterns import WeekdayPattern
from resonance.analysis.trends import TrendResult
from resonance.report.generator import (
    Report,
    format_json,
    format_markdown,
    format_text,
    generate_report_from_df,
)


@pytest.fixture
def sample_df():
    """Create a sample DataFrame with data."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60)
    base = np.random.randn(60).cumsum()
    return pd.DataFrame(
        {
            "steps": base * 1000 + 5000,
            "mood": base * 0.3 + 5 + np.random.randn(60) * 0.5,
            "sleep": np.random.randn(60) * 1.5 + 7,
        },
        index=dates,
    )


@pytest.fixture
def sample_report():
    """Create a sample report for formatting tests."""
    return Report(
        date_range=("2024-01-01", "2024-01-07"),
        patterns=[
            CorrelationResult("steps", "mood", 0.65, 0.001, 50, 0, "high"),
            CorrelationResult("sleep", "energy", -0.45, 0.02, 30, 1, "medium"),
        ],
        weekday_effects=[
            WeekdayPattern("steps", 0, "Monday", 8000, 6000, 33.3, True),
        ],
        trends=[
            TrendResult("steps", 5000, 6000, 20.0, "up"),
            TrendResult("mood", 5.0, 5.1, 2.0, "stable"),
        ],
        data_quality={
            "steps": (55, 60),
            "mood": (60, 60),
        },
    )


class TestGenerateReport:
    def test_generate_weekly_report(self, sample_df):
        """Should generate a weekly report."""
        report = generate_report_from_df(
            sample_df, period="week", reference_date=date(2024, 2, 15)
        )
        assert report.date_range[0] == "2024-02-08"
        assert report.date_range[1] == "2024-02-15"

    def test_generate_monthly_report(self, sample_df):
        """Should generate a monthly report."""
        report = generate_report_from_df(
            sample_df, period="month", reference_date=date(2024, 2, 15)
        )
        assert report.date_range[0] == "2024-01-16"
        assert report.date_range[1] == "2024-02-15"

    def test_generate_quarterly_report(self, sample_df):
        """Should generate a quarterly report (90 days)."""
        report = generate_report_from_df(
            sample_df, period="quarter", reference_date=date(2024, 4, 1)
        )
        assert report.date_range[0] == "2024-01-02"
        assert report.date_range[1] == "2024-04-01"

    def test_generate_yearly_report(self, sample_df):
        """Should generate a yearly report (365 days)."""
        report = generate_report_from_df(
            sample_df, period="year", reference_date=date(2024, 12, 31)
        )
        assert report.date_range[0] == "2024-01-01"
        assert report.date_range[1] == "2024-12-31"

    def test_report_date_range_correct(self, sample_df):
        """Date range should match period."""
        report = generate_report_from_df(
            sample_df, period="week", reference_date=date(2024, 2, 10)
        )
        # Week: 7 days back from Feb 10 = Feb 3
        assert report.date_range == ("2024-02-03", "2024-02-10")

    def test_report_includes_patterns(self, sample_df):
        """Report should include correlation patterns."""
        report = generate_report_from_df(sample_df)
        assert isinstance(report.patterns, list)
        # May or may not find patterns depending on data

    def test_report_includes_weekday_effects(self, sample_df):
        """Report should include weekday effects."""
        report = generate_report_from_df(sample_df)
        assert isinstance(report.weekday_effects, list)

    def test_report_includes_trends(self, sample_df):
        """Report should include trends."""
        report = generate_report_from_df(
            sample_df, reference_date=date(2024, 2, 15)
        )
        assert isinstance(report.trends, list)

    def test_report_includes_data_quality(self, sample_df):
        """Report should include data quality metrics."""
        report = generate_report_from_df(sample_df)
        assert isinstance(report.data_quality, dict)
        assert "steps" in report.data_quality
        days, total = report.data_quality["steps"]
        assert days <= total

    def test_handle_empty_dataframe(self):
        """Should handle empty DataFrame."""
        df = pd.DataFrame()
        report = generate_report_from_df(df, reference_date=date(2024, 2, 15))
        assert report.patterns == []
        assert report.weekday_effects == []
        assert report.trends == []

    def test_filter_none_trends(self, sample_df):
        """Should filter out None trends."""
        report = generate_report_from_df(sample_df)
        assert all(t is not None for t in report.trends)

    def test_data_quality_percentages(self, sample_df):
        """Data quality should show correct counts."""
        # Add some NaN values
        sample_df.iloc[0:5, 0] = np.nan
        report = generate_report_from_df(sample_df)
        steps_days, steps_total = report.data_quality["steps"]
        assert steps_days == 55  # 60 - 5 NaN
        assert steps_total == 60


class TestFormatJson:
    def test_format_json_valid(self, sample_report):
        """Should produce valid JSON."""
        result = format_json(sample_report)
        parsed = json.loads(result)
        assert "date_range" in parsed
        assert "patterns" in parsed

    def test_format_json_includes_all_fields(self, sample_report):
        """JSON should include all report fields."""
        result = format_json(sample_report)
        parsed = json.loads(result)
        assert parsed["date_range"] == ["2024-01-01", "2024-01-07"]
        assert len(parsed["patterns"]) == 2
        assert len(parsed["weekday_effects"]) == 1
        assert len(parsed["trends"]) == 2


class TestFormatText:
    def test_format_text(self, sample_report):
        """Should produce readable text."""
        result = format_text(sample_report)
        assert "Resonance Report" in result
        assert "2024-01-01" in result
        assert "steps" in result

    def test_format_text_no_patterns(self):
        """Should handle no patterns gracefully."""
        report = Report(date_range=("2024-01-01", "2024-01-07"))
        result = format_text(report)
        assert "No significant correlations found" in result

    def test_format_text_no_trends(self):
        """Should handle no trends gracefully."""
        report = Report(date_range=("2024-01-01", "2024-01-07"))
        result = format_text(report)
        assert "No trend data available" in result


class TestFormatMarkdown:
    def test_format_markdown(self, sample_report):
        """Should produce valid Markdown."""
        result = format_markdown(sample_report)
        assert "# Resonance Report" in result
        assert "## Correlations" in result
        assert "|" in result  # Tables

    def test_format_markdown_tables(self, sample_report):
        """Should include Markdown tables."""
        result = format_markdown(sample_report)
        assert "| Metrics |" in result
        assert "| Metric |" in result
