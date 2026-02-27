"""Tests for TUI dashboard rendering."""

import pytest
from io import StringIO
from rich.console import Console

from resonance.report.generator import Report
from resonance.analysis.correlation import CorrelationResult
from resonance.analysis.patterns import WeekdayPattern
from resonance.analysis.trends import TrendResult
from resonance.report.tui import (
    _sparkline_ascii,
    _correlation_color,
    render_patterns_panel,
    render_weekday_panel,
    render_trends_panel,
    render_quality_panel,
    render_dashboard,
    render_correlation_heatmap,
)


class TestSparklineAscii:
    """Tests for ASCII sparkline generation."""
    
    def test_empty_values(self):
        result = _sparkline_ascii([])
        assert result == "-" * 20
    
    def test_single_value(self):
        result = _sparkline_ascii([5])
        assert result == "-" * 20
    
    def test_increasing_values(self):
        result = _sparkline_ascii([1, 2, 3, 4, 5], width=5)
        assert "▁" in result or "▂" in result
        assert "█" in result or "▇" in result
    
    def test_flat_values(self):
        result = _sparkline_ascii([5, 5, 5, 5], width=4)
        # Should use middle character for flat line
        assert len(result) == 4
    
    def test_downsampling(self):
        # More values than width should downsample
        values = list(range(100))
        result = _sparkline_ascii(values, width=10)
        assert len(result) == 10


class TestCorrelationColor:
    """Tests for correlation color mapping."""
    
    def test_strong_positive(self):
        assert _correlation_color(0.8) == "green"
    
    def test_moderate_positive(self):
        assert _correlation_color(0.5) == "yellow"
    
    def test_strong_negative(self):
        assert _correlation_color(-0.8) == "red"
    
    def test_moderate_negative(self):
        assert _correlation_color(-0.5) == "magenta"
    
    def test_weak_correlation(self):
        assert _correlation_color(0.1) == "white"
        assert _correlation_color(-0.1) == "white"


class TestPanelRendering:
    """Tests for panel rendering functions."""
    
    @pytest.fixture
    def sample_report(self):
        """Create a sample report for testing."""
        return Report(
            date_range=("2026-02-01", "2026-02-28"),
            patterns=[
                CorrelationResult(
                    metric1="sleep_hours",
                    metric2="energy",
                    correlation=0.75,
                    p_value=0.001,
                    sample_size=28,
                    lag_days=0,
                    confidence="high",
                ),
                CorrelationResult(
                    metric1="steps",
                    metric2="mood",
                    correlation=0.45,
                    p_value=0.02,
                    sample_size=28,
                    lag_days=1,
                    confidence="medium",
                ),
            ],
            weekday_effects=[
                WeekdayPattern(
                    metric="energy",
                    weekday=5,  # Saturday
                    weekday_name="Saturday",
                    mean=8.0,
                    overall_mean=6.5,
                    difference_pct=0.23,
                    significant=True,
                ),
            ],
            trends=[
                TrendResult(
                    metric="sleep_hours",
                    period1_mean=7.0,
                    period2_mean=7.5,
                    change_pct=0.07,
                    direction="up",
                ),
            ],
            data_quality={
                "sleep_hours": (28, 28),
                "energy": (25, 28),
                "steps": (20, 28),
            }
        )
    
    @pytest.fixture
    def empty_report(self):
        """Create an empty report."""
        return Report(date_range=("2026-02-01", "2026-02-28"))
    
    def test_patterns_panel_with_data(self, sample_report):
        panel = render_patterns_panel(sample_report)
        assert panel.title is not None
        assert "Patterns" in str(panel.title)
    
    def test_patterns_panel_empty(self, empty_report):
        panel = render_patterns_panel(empty_report)
        assert panel is not None
    
    def test_weekday_panel_with_data(self, sample_report):
        panel = render_weekday_panel(sample_report)
        assert "Weekday" in str(panel.title)
    
    def test_weekday_panel_empty(self, empty_report):
        panel = render_weekday_panel(empty_report)
        assert panel is not None
    
    def test_trends_panel_with_data(self, sample_report):
        panel = render_trends_panel(sample_report)
        assert "Trends" in str(panel.title)
    
    def test_trends_panel_empty(self, empty_report):
        panel = render_trends_panel(empty_report)
        assert panel is not None
    
    def test_quality_panel_with_data(self, sample_report):
        panel = render_quality_panel(sample_report)
        assert "Quality" in str(panel.title)
    
    def test_quality_panel_empty(self, empty_report):
        panel = render_quality_panel(empty_report)
        assert panel is not None


class TestDashboard:
    """Tests for full dashboard rendering."""
    
    @pytest.fixture
    def sample_report(self):
        return Report(
            date_range=("2026-02-01", "2026-02-28"),
            patterns=[
                CorrelationResult(
                    metric1="sleep",
                    metric2="energy",
                    correlation=0.7,
                    p_value=0.001,
                    confidence="high",
                    sample_size=28,
                    lag_days=0
                )
            ],
            weekday_effects=[],
            trends=[],
            data_quality={"sleep": (28, 28)}
        )
    
    def test_render_dashboard(self, sample_report):
        # Just verify it doesn't crash
        console = Console(file=StringIO(), force_terminal=True)
        render_dashboard(sample_report, console=console)
        output = console.file.getvalue()
        assert "Resonance Dashboard" in output
    
    def test_render_dashboard_empty(self):
        report = Report(date_range=("2026-02-01", "2026-02-28"))
        console = Console(file=StringIO(), force_terminal=True)
        render_dashboard(report, console=console)
        # Should not crash with empty data


class TestCorrelationHeatmap:
    """Tests for correlation heatmap rendering."""
    
    def test_heatmap_with_data(self):
        report = Report(
            date_range=("2026-02-01", "2026-02-28"),
            patterns=[
                CorrelationResult(
                    metric1="A", metric2="B", correlation=0.8,
                    p_value=0.001, confidence="high", sample_size=28, lag_days=0
                ),
                CorrelationResult(
                    metric1="A", metric2="C", correlation=-0.6,
                    p_value=0.01, confidence="medium", sample_size=28, lag_days=0
                ),
            ]
        )
        console = Console(file=StringIO(), force_terminal=True)
        render_correlation_heatmap(report, console=console)
        output = console.file.getvalue()
        assert "A" in output
        assert "B" in output
    
    def test_heatmap_empty(self):
        report = Report(date_range=("2026-02-01", "2026-02-28"))
        console = Console(file=StringIO(), force_terminal=True)
        render_correlation_heatmap(report, console=console)
        output = console.file.getvalue()
        assert "No correlations" in output
