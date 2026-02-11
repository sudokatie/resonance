"""Tests for automated daily report generation."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock
from io import StringIO

from resonance.report.daily import (
    DailyReportConfig,
    load_daily_config,
    generate_daily_report,
    deliver_report,
    run_daily,
    _markdown_to_html,
)
from resonance.report.generator import Report


@pytest.fixture
def sample_report():
    """Create a sample report for testing."""
    from resonance.analysis.correlation import CorrelationResult
    from resonance.analysis.trends import TrendResult
    from resonance.analysis.patterns import WeekdayPattern
    
    return Report(
        date_range=("2024-01-01", "2024-01-07"),
        patterns=[
            CorrelationResult(
                metric1="steps",
                metric2="mood",
                correlation=0.65,
                p_value=0.01,
                lag_days=0,
                sample_size=30,
                confidence="high",
            )
        ],
        weekday_effects=[
            WeekdayPattern(
                metric="steps",
                weekday=0,
                weekday_name="Monday",
                mean=8000.0,
                overall_mean=7000.0,
                difference_pct=14.3,
                significant=True,
            )
        ],
        trends=[
            TrendResult(
                metric="steps",
                period1_mean=6790.0,
                period2_mean=7500.0,
                change_pct=10.5,
                direction="up",
            )
        ],
        data_quality={"steps": (7, 7), "mood": (5, 7)},
    )


class TestDailyReportConfig:
    """Tests for DailyReportConfig."""

    def test_default_values(self):
        """Default config has sensible values."""
        config = DailyReportConfig()
        assert config.enabled is False
        assert config.delivery == "stdout"
        assert config.min_data_days == 7

    def test_custom_values(self):
        """Config accepts custom values."""
        config = DailyReportConfig(
            enabled=True,
            delivery="email",
            email_to="test@example.com",
            min_data_days=14,
        )
        assert config.enabled is True
        assert config.delivery == "email"
        assert config.email_to == "test@example.com"
        assert config.min_data_days == 14


class TestLoadDailyConfig:
    """Tests for load_daily_config function."""

    def test_loads_defaults_when_no_file(self, tmp_path):
        """Returns defaults when config file doesn't exist."""
        with patch("resonance.report.daily.get_config_path", return_value=tmp_path / "nonexistent.toml"):
            config = load_daily_config()
        
        assert config.enabled is False
        assert config.delivery == "stdout"

    def test_loads_from_file(self, tmp_path):
        """Loads values from TOML file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[daily]
enabled = true
delivery = "file"
min_data_days = 14
email_to = "user@example.com"
""")
        
        with patch("resonance.report.daily.get_config_path", return_value=config_file):
            config = load_daily_config()
        
        assert config.enabled is True
        assert config.delivery == "file"
        assert config.min_data_days == 14
        assert config.email_to == "user@example.com"


class TestGenerateDailyReport:
    """Tests for generate_daily_report function."""

    def test_returns_none_with_insufficient_data(self):
        """Returns None when not enough data."""
        db = MagicMock()
        db.get_metrics_df.return_value = MagicMock(empty=True)
        
        with patch("resonance.report.daily.generate_report") as mock_gen:
            mock_gen.return_value = Report(
                date_range=("2024-01-01", "2024-01-07"),
                data_quality={"steps": (3, 7)},  # Only 3 days
            )
            config = DailyReportConfig(min_data_days=7)
            result = generate_daily_report(db, config=config)
        
        assert result is None

    def test_returns_report_with_sufficient_data(self):
        """Returns report when enough data."""
        db = MagicMock()
        
        with patch("resonance.report.daily.generate_report") as mock_gen:
            mock_gen.return_value = Report(
                date_range=("2024-01-01", "2024-01-07"),
                data_quality={"steps": (7, 7), "mood": (7, 7)},  # 14 data days total
            )
            config = DailyReportConfig(min_data_days=7)
            result = generate_daily_report(db, config=config)
        
        assert result is not None

    def test_filters_sections_based_on_config(self):
        """Filters report sections based on config."""
        db = MagicMock()
        
        with patch("resonance.report.daily.generate_report") as mock_gen:
            mock_gen.return_value = Report(
                date_range=("2024-01-01", "2024-01-07"),
                patterns=[MagicMock()],
                trends=[MagicMock()],
                weekday_effects=[MagicMock()],
                data_quality={"steps": (10, 10)},
            )
            config = DailyReportConfig(
                min_data_days=5,
                include_trends=False,
                include_correlations=False,
                include_weekday=True,
            )
            result = generate_daily_report(db, config=config)
        
        assert result.patterns == []
        assert result.trends == []
        assert len(result.weekday_effects) == 1


class TestDeliverReport:
    """Tests for deliver_report function."""

    def test_deliver_stdout(self, sample_report, capsys):
        """Delivers to stdout."""
        config = DailyReportConfig(delivery="stdout")
        result = deliver_report(sample_report, config)
        
        assert result is True
        captured = capsys.readouterr()
        assert "Resonance Report" in captured.out
        assert "steps" in captured.out

    def test_deliver_file(self, sample_report, tmp_path):
        """Delivers to file."""
        with patch("resonance.report.daily.Path.home", return_value=tmp_path):
            config = DailyReportConfig(delivery="file")
            result = deliver_report(sample_report, config)
        
        assert result is True
        reports_dir = tmp_path / ".config" / "resonance" / "reports"
        assert reports_dir.exists()
        report_files = list(reports_dir.glob("report-*.md"))
        assert len(report_files) == 1

    def test_deliver_notification_failure_graceful(self, sample_report):
        """Notification delivery fails gracefully."""
        with patch("subprocess.run", side_effect=Exception("No osascript")):
            config = DailyReportConfig(delivery="notification")
            result = deliver_report(sample_report, config)
        
        assert result is False


class TestMarkdownToHtml:
    """Tests for markdown to HTML conversion."""

    def test_converts_headers(self):
        """Converts markdown headers to HTML."""
        md = "# Title\n## Section"
        html = _markdown_to_html(md)
        assert "<h1>Title</h1>" in html
        assert "<h2>Section</h2>" in html

    def test_converts_bold(self):
        """Converts bold text."""
        md = "This is **bold** text"
        html = _markdown_to_html(md)
        assert "<strong>bold</strong>" in html

    def test_converts_tables(self):
        """Converts markdown tables to HTML."""
        md = """| A | B |
|---|---|
| 1 | 2 |"""
        html = _markdown_to_html(md)
        assert "<table" in html
        assert "<td>1</td>" in html


class TestRunDaily:
    """Tests for run_daily function."""

    def test_returns_false_with_no_data(self):
        """Returns False when no report generated."""
        with patch("resonance.report.daily.Database") as mock_db:
            with patch("resonance.report.daily.generate_daily_report", return_value=None):
                result = run_daily(force=False)
        
        assert result is False

    def test_force_generates_with_little_data(self):
        """Force flag generates even with little data."""
        with patch("resonance.report.daily.Database") as mock_db:
            with patch("resonance.report.daily.generate_daily_report") as mock_gen:
                with patch("resonance.report.daily.deliver_report", return_value=True):
                    mock_gen.return_value = Report(
                        date_range=("2024-01-01", "2024-01-07"),
                        data_quality={"steps": (2, 7)},
                    )
                    result = run_daily(force=True)
        
        # When force=True, min_data_days is set to 0
        assert mock_gen.called
