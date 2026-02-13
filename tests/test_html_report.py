"""Tests for HTML report generation."""

from datetime import date

import pandas as pd
import pytest

from resonance.report.generator import Report
from resonance.report.html import (
    format_html,
    _generate_sparkline_svg,
    _generate_heatmap_cell,
)
from resonance.analysis.correlation import CorrelationResult
from resonance.analysis.patterns import WeekdayPattern
from resonance.analysis.trends import TrendResult


class TestSparklineSVG:
    """Tests for sparkline generation."""

    def test_empty_values_returns_dash(self):
        result = _generate_sparkline_svg([])
        assert "-" in result

    def test_single_value_returns_dash(self):
        result = _generate_sparkline_svg([5.0])
        assert "-" in result

    def test_multiple_values_returns_svg(self):
        result = _generate_sparkline_svg([1.0, 2.0, 3.0])
        assert "<svg" in result
        assert "polyline" in result

    def test_upward_trend_uses_green(self):
        result = _generate_sparkline_svg([1.0, 2.0, 3.0])
        assert "#22c55e" in result  # green

    def test_downward_trend_uses_red(self):
        result = _generate_sparkline_svg([3.0, 2.0, 1.0])
        assert "#ef4444" in result  # red

    def test_flat_line_uses_gray(self):
        result = _generate_sparkline_svg([5.0, 5.0, 5.0])
        assert "#888888" in result  # gray


class TestHeatmapCell:
    """Tests for heatmap cell generation."""

    def test_positive_correlation_blue(self):
        result = _generate_heatmap_cell(0.8)
        assert "background" in result
        assert "0.80" in result

    def test_negative_correlation_red(self):
        result = _generate_heatmap_cell(-0.8)
        assert "background" in result
        assert "-0.80" in result

    def test_zero_correlation_white(self):
        result = _generate_heatmap_cell(0.0)
        assert "0.00" in result


class TestFormatHtml:
    """Tests for full HTML report generation."""

    def test_empty_report_generates_html(self):
        report = Report(date_range=("2024-01-01", "2024-01-31"))
        result = format_html(report)
        
        assert "<!DOCTYPE html>" in result
        assert "Resonance Report" in result
        assert "2024-01-01" in result
        assert "2024-01-31" in result

    def test_report_with_patterns(self):
        report = Report(
            date_range=("2024-01-01", "2024-01-31"),
            patterns=[
                CorrelationResult(
                    metric1="sleep",
                    metric2="energy",
                    correlation=0.75,
                    p_value=0.01,
                    lag_days=1,
                    sample_size=30,
                    confidence="high",
                )
            ],
        )
        result = format_html(report)
        
        assert "sleep" in result
        assert "energy" in result
        assert "0.75" in result
        assert "high" in result

    def test_report_with_weekday_patterns(self):
        report = Report(
            date_range=("2024-01-01", "2024-01-31"),
            weekday_effects=[
                WeekdayPattern(
                    metric="steps",
                    weekday=0,
                    weekday_name="Monday",
                    mean=8000.0,
                    overall_mean=10000.0,
                    difference_pct=-20.0,
                    significant=True,
                )
            ],
        )
        result = format_html(report)
        
        assert "Monday" in result
        assert "steps" in result
        assert "20%" in result

    def test_report_with_trends(self):
        report = Report(
            date_range=("2024-01-01", "2024-01-31"),
            trends=[
                TrendResult(
                    metric="weight",
                    period1_mean=72.0,
                    period2_mean=70.0,
                    change_pct=-2.8,
                    direction="down",
                )
            ],
        )
        result = format_html(report)
        
        assert "weight" in result
        assert "Trends" in result

    def test_report_with_data_quality(self):
        report = Report(
            date_range=("2024-01-01", "2024-01-31"),
            data_quality={"steps": (28, 31), "sleep": (25, 31)},
        )
        result = format_html(report)
        
        assert "Data Quality" in result
        assert "28/31" in result
        assert "25/31" in result

    def test_report_with_dataframe_generates_sparklines(self):
        report = Report(
            date_range=("2024-01-01", "2024-01-14"),
            trends=[
                TrendResult(
                    metric="steps",
                    period1_mean=8000.0,
                    period2_mean=10000.0,
                    change_pct=25.0,
                    direction="up",
                )
            ],
        )
        
        # Create sample DataFrame
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=14),
            "steps": [8000, 8500, 9000, 9200, 9500, 9800, 10000, 10200, 10500, 10800, 11000, 11200, 11500, 12000],
        })
        
        result = format_html(report, df=df)
        
        assert "<svg" in result  # Sparkline present

    def test_custom_title(self):
        report = Report(date_range=("2024-01-01", "2024-01-31"))
        result = format_html(report, title="My Custom Report")
        
        assert "My Custom Report" in result

    def test_html_escaping(self):
        """Ensure HTML special characters are escaped."""
        report = Report(
            date_range=("2024-01-01", "2024-01-31"),
            patterns=[
                CorrelationResult(
                    metric1="<script>alert('xss')</script>",
                    metric2="normal",
                    correlation=0.5,
                    p_value=0.05,
                    lag_days=0,
                    sample_size=30,
                    confidence="medium",
                )
            ],
        )
        result = format_html(report)
        
        # Should be escaped, not raw script tag
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestHtmlReportStructure:
    """Tests for HTML structure and styling."""

    def test_contains_required_sections(self):
        report = Report(
            date_range=("2024-01-01", "2024-01-31"),
            patterns=[
                CorrelationResult("a", "b", 0.5, 0.05, 0, 30, "medium")
            ],
            weekday_effects=[
                WeekdayPattern(
                    metric="a",
                    weekday=0,
                    weekday_name="Monday",
                    mean=100.0,
                    overall_mean=90.0,
                    difference_pct=10.0,
                    significant=True,
                )
            ],
            trends=[
                TrendResult(metric="a", period1_mean=90.0, period2_mean=100.0, change_pct=10.0, direction="up")
            ],
            data_quality={"a": (30, 31)},
        )
        result = format_html(report)
        
        assert "Correlations" in result
        assert "Weekday Patterns" in result
        assert "Trends" in result
        assert "Data Quality" in result

    def test_responsive_design_viewport(self):
        report = Report(date_range=("2024-01-01", "2024-01-31"))
        result = format_html(report)
        
        assert 'name="viewport"' in result

    def test_self_contained_no_external_deps(self):
        """HTML should be self-contained with no external CSS/JS."""
        report = Report(date_range=("2024-01-01", "2024-01-31"))
        result = format_html(report)
        
        # Should have inline styles
        assert "<style>" in result
        # Should not have external links
        assert 'href="http' not in result
        assert 'src="http' not in result
