"""Tests for Oura integration."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from resonance.ingest.oura import (
    get_supported_metrics,
    get_token_path,
    get_valid_token,
    load_token,
    parse_activity_metrics,
    parse_readiness_metrics,
    parse_sleep_metrics,
    save_token,
    ACTIVITY_METRICS,
    READINESS_METRICS,
    SLEEP_METRICS,
)
from resonance.models import MetricRecord


class TestTokenStorage:
    """Tests for token storage."""
    
    def test_get_token_path(self):
        """Get path to token file."""
        path = get_token_path()
        assert path.name == "oura_token.json"
        assert ".config/resonance" in str(path)
    
    def test_save_and_load_token(self, tmp_path):
        """Save and load token."""
        token_path = tmp_path / "token.json"
        with patch("resonance.ingest.oura.get_token_path", return_value=token_path):
            save_token("test_token_123")
            loaded = load_token()
        
        assert loaded == "test_token_123"
    
    def test_load_token_missing(self, tmp_path):
        """Load returns None when file missing."""
        token_path = tmp_path / "nonexistent.json"
        with patch("resonance.ingest.oura.get_token_path", return_value=token_path):
            loaded = load_token()
        assert loaded is None
    
    def test_load_token_invalid_json(self, tmp_path):
        """Load returns None for invalid JSON."""
        token_path = tmp_path / "invalid.json"
        token_path.write_text("not json")
        with patch("resonance.ingest.oura.get_token_path", return_value=token_path):
            loaded = load_token()
        assert loaded is None


class TestGetValidToken:
    """Tests for get_valid_token."""
    
    def test_uses_provided_token(self, tmp_path):
        """Uses provided token and saves it."""
        token_path = tmp_path / "token.json"
        with patch("resonance.ingest.oura.get_token_path", return_value=token_path):
            result = get_valid_token("new_token")
        
        assert result == "new_token"
        assert token_path.exists()
    
    def test_loads_saved_token(self, tmp_path):
        """Loads saved token when none provided."""
        token_path = tmp_path / "token.json"
        token_path.write_text('{"token": "saved_token"}')
        
        with patch("resonance.ingest.oura.get_token_path", return_value=token_path):
            result = get_valid_token()
        
        assert result == "saved_token"
    
    def test_raises_when_no_token(self, tmp_path):
        """Raises ValueError when no token available."""
        token_path = tmp_path / "nonexistent.json"
        with patch("resonance.ingest.oura.get_token_path", return_value=token_path):
            with pytest.raises(ValueError, match="No Oura API token"):
                get_valid_token()


class TestParseSleepMetrics:
    """Tests for sleep metrics parsing."""
    
    def test_parse_sleep_hours(self):
        """Parse total sleep duration."""
        records = [
            {
                "day": "2024-01-15",
                "total_sleep_duration": 25200,  # 7 hours in seconds
            }
        ]
        metrics = parse_sleep_metrics(records)
        sleep_hours = [m for m in metrics if m.metric_name == "sleep_hours"]
        
        assert len(sleep_hours) == 1
        assert sleep_hours[0].date == "2024-01-15"
        assert sleep_hours[0].value == 7.0
        assert sleep_hours[0].source == "oura"
    
    def test_parse_multiple_sleep_metrics(self):
        """Parse multiple sleep metrics from one record."""
        records = [
            {
                "day": "2024-01-15",
                "total_sleep_duration": 28800,  # 8 hours
                "efficiency": 95,
                "deep_sleep_duration": 7200,  # 2 hours
                "average_heart_rate": 55,
                "average_hrv": 45,
            }
        ]
        metrics = parse_sleep_metrics(records)
        
        assert len(metrics) == 5
        metric_names = {m.metric_name for m in metrics}
        assert "sleep_hours" in metric_names
        assert "sleep_efficiency" in metric_names
        assert "deep_sleep_hours" in metric_names
        assert "sleep_hr_avg" in metric_names
        assert "hrv_avg" in metric_names
    
    def test_parse_sleep_missing_fields(self):
        """Parse sleep record with missing fields."""
        records = [
            {
                "day": "2024-01-15",
                "total_sleep_duration": 28800,
            }
        ]
        metrics = parse_sleep_metrics(records)
        
        # Should only have sleep_hours, not other fields
        assert len(metrics) == 1
        assert metrics[0].metric_name == "sleep_hours"
    
    def test_parse_sleep_no_day(self):
        """Skip records without day field."""
        records = [{"total_sleep_duration": 28800}]
        metrics = parse_sleep_metrics(records)
        assert len(metrics) == 0


class TestParseReadinessMetrics:
    """Tests for readiness metrics parsing."""
    
    def test_parse_readiness_score(self):
        """Parse readiness score."""
        records = [
            {
                "day": "2024-01-15",
                "score": 85,
            }
        ]
        metrics = parse_readiness_metrics(records)
        
        assert len(metrics) == 1
        assert metrics[0].metric_name == "readiness_score"
        assert metrics[0].value == 85.0
        assert metrics[0].date == "2024-01-15"
    
    def test_parse_temp_deviation(self):
        """Parse temperature deviation."""
        records = [
            {
                "day": "2024-01-15",
                "temperature_deviation": 0.3,
            }
        ]
        metrics = parse_readiness_metrics(records)
        
        assert len(metrics) == 1
        assert metrics[0].metric_name == "temp_deviation"
        assert metrics[0].value == 0.3


class TestParseActivityMetrics:
    """Tests for activity metrics parsing."""
    
    def test_parse_steps(self):
        """Parse step count."""
        records = [
            {
                "day": "2024-01-15",
                "steps": 10000,
            }
        ]
        metrics = parse_activity_metrics(records)
        
        steps_metric = [m for m in metrics if m.metric_name == "steps"]
        assert len(steps_metric) == 1
        assert steps_metric[0].value == 10000
    
    def test_parse_distance_conversion(self):
        """Parse distance with meters to km conversion."""
        records = [
            {
                "day": "2024-01-15",
                "equivalent_walking_distance": 5000,  # meters
            }
        ]
        metrics = parse_activity_metrics(records)
        
        distance_metric = [m for m in metrics if m.metric_name == "distance_km"]
        assert len(distance_metric) == 1
        assert distance_metric[0].value == 5.0  # km
    
    def test_parse_all_activity_metrics(self):
        """Parse all activity metrics."""
        records = [
            {
                "day": "2024-01-15",
                "steps": 10000,
                "active_calories": 500,
                "total_calories": 2000,
                "equivalent_walking_distance": 8000,
            }
        ]
        metrics = parse_activity_metrics(records)
        
        assert len(metrics) == 4
        metric_names = {m.metric_name for m in metrics}
        assert "steps" in metric_names
        assert "active_calories" in metric_names
        assert "total_calories" in metric_names
        assert "distance_km" in metric_names


class TestSupportedMetrics:
    """Tests for supported metrics."""
    
    def test_get_supported_metrics(self):
        """Get list of supported metrics."""
        metrics = get_supported_metrics()
        
        # Sleep metrics
        assert "sleep_hours" in metrics
        assert "hrv_avg" in metrics
        
        # Readiness metrics
        assert "readiness_score" in metrics
        
        # Activity metrics
        assert "steps" in metrics
    
    def test_metrics_sorted(self):
        """Metrics list is sorted."""
        metrics = get_supported_metrics()
        assert metrics == sorted(metrics)
    
    def test_metric_definitions_complete(self):
        """All metric definitions have required fields."""
        for api_field, metric_name, transform in SLEEP_METRICS:
            assert isinstance(api_field, str)
            assert isinstance(metric_name, str)
            assert callable(transform)
        
        for api_field, metric_name, transform in READINESS_METRICS:
            assert isinstance(api_field, str)
            assert isinstance(metric_name, str)
            assert callable(transform)
        
        for api_field, metric_name, transform in ACTIVITY_METRICS:
            assert isinstance(api_field, str)
            assert isinstance(metric_name, str)
            assert callable(transform)
