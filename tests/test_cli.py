"""Tests for CLI commands."""

from pathlib import Path
from typer.testing import CliRunner

import pytest

from resonance.cli import app


runner = CliRunner()


class TestCLI:
    def test_version(self):
        """Should show version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "resonance" in result.output

    def test_help(self):
        """Should show help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Find patterns in your life" in result.output

    def test_ingest_file_not_found(self):
        """Should error on missing file."""
        result = runner.invoke(app, ["ingest", "health", "/nonexistent/path.xml"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_ingest_unknown_source(self, tmp_path):
        """Should error on unknown source."""
        # Create a dummy file
        dummy = tmp_path / "test.txt"
        dummy.write_text("test")
        result = runner.invoke(app, ["ingest", "unknown", str(dummy)])
        assert result.exit_code == 1
        assert "Unknown source" in result.output

    def test_status_empty(self, tmp_path, monkeypatch):
        """Should show no data message when empty."""
        # Use a temp database
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "No data yet" in result.output

    def test_log_command(self, tmp_path, monkeypatch):
        """Should log a metric."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["log", "mood", "7"])
        assert result.exit_code == 0
        assert "Logged mood=7" in result.output

    def test_analyze_empty(self, tmp_path, monkeypatch):
        """Should handle empty database."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 0
        assert "No data found" in result.output

    def test_report_empty(self, tmp_path, monkeypatch):
        """Should generate empty report."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["report"])
        assert result.exit_code == 0
        assert "Report" in result.output or "No" in result.output

    def test_report_json_format(self, tmp_path, monkeypatch):
        """Should output JSON when requested."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["report", "--format", "json"])
        assert result.exit_code == 0
        assert "{" in result.output  # JSON starts with {

    def test_report_markdown_format(self, tmp_path, monkeypatch):
        """Should output Markdown when requested."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["report", "--format", "markdown"])
        assert result.exit_code == 0
        assert "#" in result.output  # Markdown headers

    def test_analyze_p_threshold_flag(self, tmp_path, monkeypatch):
        """Should accept --p-threshold flag."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["analyze", "--p-threshold", "0.01"])
        assert result.exit_code == 0

    def test_analyze_min_correlation_flag(self, tmp_path, monkeypatch):
        """Should accept --min-correlation flag."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, ["analyze", "--min-correlation", "0.5"])
        assert result.exit_code == 0

    def test_analyze_all_flags(self, tmp_path, monkeypatch):
        """Should accept all analyze flags together."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        result = runner.invoke(app, [
            "analyze",
            "--min-days", "7",
            "--p-threshold", "0.01",
            "--min-correlation", "0.5",
            "--lag", "3",
        ])
        assert result.exit_code == 0
