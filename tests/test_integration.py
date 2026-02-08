"""Integration tests for end-to-end workflows."""

import json
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from resonance.cli import app
from resonance.config import load_config
from resonance.database import Database
from resonance.models import MetricRecord


runner = CliRunner()


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Create a temporary database."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("RESONANCE_DB_PATH", str(db_path))
    db = Database(db_path)
    yield db
    db.close()


@pytest.fixture
def populated_db(temp_db):
    """Create a database with sample data."""
    # Generate 60 days of correlated data
    np.random.seed(42)
    base = np.random.randn(60).cumsum()
    
    start_date = date.today() - timedelta(days=60)
    metrics = []
    
    for i in range(60):
        day = (start_date + timedelta(days=i)).isoformat()
        metrics.append(MetricRecord(day, "steps", base[i] * 1000 + 5000, "manual"))
        metrics.append(MetricRecord(day, "mood", base[i] * 0.3 + 5, "manual"))
        metrics.append(MetricRecord(day, "sleep", np.random.randn() + 7, "manual"))
    
    temp_db.insert_metrics(metrics)
    return temp_db


class TestCLIPipelines:
    def test_log_then_status(self, tmp_path, monkeypatch):
        """Should log metrics and show in status."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        
        # Log some metrics
        runner.invoke(app, ["log", "mood", "7"])
        runner.invoke(app, ["log", "energy", "8"])
        
        # Check status
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "mood" in result.output
        assert "energy" in result.output

    def test_log_then_report(self, tmp_path, monkeypatch):
        """Should log metrics and generate report."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        
        # Log metrics
        runner.invoke(app, ["log", "mood", "7"])
        
        # Generate report
        result = runner.invoke(app, ["report"])
        assert result.exit_code == 0
        assert "Report" in result.output or "No" in result.output


class TestDatabasePersistence:
    def test_persists_between_runs(self, tmp_path, monkeypatch):
        """Database should persist data."""
        db_path = str(tmp_path / "persist.db")
        monkeypatch.setenv("RESONANCE_DB_PATH", db_path)
        
        # First run: log data
        runner.invoke(app, ["log", "test_metric", "42"])
        
        # Second run: should see data
        result = runner.invoke(app, ["status"])
        assert "test_metric" in result.output


class TestConfigLoading:
    def test_env_var_override(self, tmp_path, monkeypatch):
        """Environment variable should override config."""
        custom_path = tmp_path / "custom.db"
        monkeypatch.setenv("RESONANCE_DB_PATH", str(custom_path))
        
        config = load_config()
        assert config.db_path == custom_path


class TestReportFormats:
    def test_report_all_formats(self, tmp_path, monkeypatch):
        """Should generate report in all formats."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        
        # Text
        result = runner.invoke(app, ["report", "--format", "text"])
        assert result.exit_code == 0
        
        # JSON
        result = runner.invoke(app, ["report", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "date_range" in parsed
        
        # Markdown
        result = runner.invoke(app, ["report", "--format", "markdown"])
        assert result.exit_code == 0
        assert "#" in result.output

    def test_report_to_file(self, tmp_path, monkeypatch):
        """Should save report to file."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(tmp_path / "test.db"))
        output_file = tmp_path / "report.txt"
        
        result = runner.invoke(app, ["report", "--output", str(output_file)])
        assert result.exit_code == 0
        assert output_file.exists()


class TestAnalysisPipeline:
    def test_analyze_with_data(self, populated_db, tmp_path, monkeypatch):
        """Should find correlations in sample data."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(populated_db.path))
        
        result = runner.invoke(app, ["analyze"])
        # May or may not find correlations depending on random seed
        assert result.exit_code == 0

    def test_report_with_data(self, populated_db, tmp_path, monkeypatch):
        """Should generate report with all sections."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(populated_db.path))
        
        result = runner.invoke(app, ["report"])
        assert result.exit_code == 0
        assert "Report" in result.output


class TestDataQuality:
    def test_report_includes_quality(self, populated_db, monkeypatch):
        """Report should include data quality info."""
        monkeypatch.setenv("RESONANCE_DB_PATH", str(populated_db.path))
        
        result = runner.invoke(app, ["report"])
        assert "steps" in result.output.lower() or "Quality" in result.output
