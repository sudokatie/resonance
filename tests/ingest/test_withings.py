"""Tests for Withings integration."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from resonance.ingest.withings import (
    WithingsCredentials,
    get_credentials_path,
    get_supported_metrics,
    load_credentials,
    parse_measure_metrics,
    parse_sleep_metrics,
    save_credentials,
    MEASURE_TYPES,
)
from resonance.models import MetricRecord


class TestWithingsCredentials:
    """Tests for WithingsCredentials."""
    
    def test_is_expired_true(self):
        """Credentials are expired when past expiry time."""
        creds = WithingsCredentials(
            access_token="test",
            refresh_token="refresh",
            expires_at=time.time() - 100,
            client_id="client",
            client_secret="secret",
            user_id="123",
        )
        assert creds.is_expired() is True
    
    def test_is_expired_false(self):
        """Credentials are not expired when within buffer."""
        creds = WithingsCredentials(
            access_token="test",
            refresh_token="refresh",
            expires_at=time.time() + 3600,
            client_id="client",
            client_secret="secret",
            user_id="123",
        )
        assert creds.is_expired() is False
    
    def test_is_expired_within_buffer(self):
        """Credentials expired when within 60s buffer."""
        creds = WithingsCredentials(
            access_token="test",
            refresh_token="refresh",
            expires_at=time.time() + 30,  # 30s from now, within 60s buffer
            client_id="client",
            client_secret="secret",
            user_id="123",
        )
        assert creds.is_expired() is True
    
    def test_to_dict(self):
        """Convert credentials to dictionary."""
        creds = WithingsCredentials(
            access_token="access",
            refresh_token="refresh",
            expires_at=1234567890.0,
            client_id="client_id",
            client_secret="client_secret",
            user_id="user123",
        )
        d = creds.to_dict()
        
        assert d["access_token"] == "access"
        assert d["refresh_token"] == "refresh"
        assert d["expires_at"] == 1234567890.0
        assert d["client_id"] == "client_id"
        assert d["client_secret"] == "client_secret"
        assert d["user_id"] == "user123"
    
    def test_from_dict(self):
        """Create credentials from dictionary."""
        d = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": 1234567890.0,
            "client_id": "client_id",
            "client_secret": "client_secret",
            "user_id": "user123",
        }
        creds = WithingsCredentials.from_dict(d)
        
        assert creds.access_token == "access"
        assert creds.refresh_token == "refresh"
        assert creds.expires_at == 1234567890.0
        assert creds.client_id == "client_id"
        assert creds.client_secret == "client_secret"
        assert creds.user_id == "user123"


class TestCredentialsStorage:
    """Tests for credentials file storage."""
    
    def test_get_credentials_path(self):
        """Get path to credentials file."""
        path = get_credentials_path()
        assert path.name == "withings_credentials.json"
        assert ".config/resonance" in str(path)
    
    def test_save_and_load_credentials(self, tmp_path):
        """Save and load credentials."""
        creds_path = tmp_path / "withings_creds.json"
        creds = WithingsCredentials(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_at=1234567890.0,
            client_id="test_client",
            client_secret="test_secret",
            user_id="123",
        )
        
        with patch("resonance.ingest.withings.get_credentials_path", return_value=creds_path):
            save_credentials(creds)
            loaded = load_credentials()
        
        assert loaded is not None
        assert loaded.access_token == "test_access"
        assert loaded.refresh_token == "test_refresh"
        assert loaded.user_id == "123"
    
    def test_load_credentials_missing(self, tmp_path):
        """Load returns None when file missing."""
        creds_path = tmp_path / "nonexistent.json"
        with patch("resonance.ingest.withings.get_credentials_path", return_value=creds_path):
            loaded = load_credentials()
        assert loaded is None
    
    def test_load_credentials_invalid_json(self, tmp_path):
        """Load returns None for invalid JSON."""
        creds_path = tmp_path / "invalid.json"
        creds_path.write_text("not json")
        with patch("resonance.ingest.withings.get_credentials_path", return_value=creds_path):
            loaded = load_credentials()
        assert loaded is None


class TestParseMeasureMetrics:
    """Tests for measure metrics parsing."""
    
    def test_parse_weight(self):
        """Parse weight measurement."""
        measure_groups = [
            {
                "date": 1705328400,  # 2024-01-15 12:00:00
                "measures": [
                    {"type": 1, "value": 75000, "unit": -3}  # 75.0 kg
                ]
            }
        ]
        metrics = parse_measure_metrics(measure_groups)
        
        assert len(metrics) == 1
        assert metrics[0].metric_name == "weight_kg"
        assert metrics[0].value == 75.0
        assert metrics[0].source == "withings"
    
    def test_parse_blood_pressure(self):
        """Parse blood pressure measurements."""
        measure_groups = [
            {
                "date": 1705328400,
                "measures": [
                    {"type": 9, "value": 80, "unit": 0},   # diastolic
                    {"type": 10, "value": 120, "unit": 0}, # systolic
                ]
            }
        ]
        metrics = parse_measure_metrics(measure_groups)
        
        assert len(metrics) == 2
        names = {m.metric_name for m in metrics}
        assert "diastolic_bp" in names
        assert "systolic_bp" in names
        
        systolic = next(m for m in metrics if m.metric_name == "systolic_bp")
        assert systolic.value == 120.0
    
    def test_parse_heart_rate(self):
        """Parse heart rate measurement."""
        measure_groups = [
            {
                "date": 1705328400,
                "measures": [
                    {"type": 11, "value": 72, "unit": 0}
                ]
            }
        ]
        metrics = parse_measure_metrics(measure_groups)
        
        assert len(metrics) == 1
        assert metrics[0].metric_name == "heart_rate"
        assert metrics[0].value == 72.0
    
    def test_parse_with_unit_power(self):
        """Parse measurement with negative unit power."""
        measure_groups = [
            {
                "date": 1705328400,
                "measures": [
                    {"type": 1, "value": 75432, "unit": -3}  # 75.432 kg
                ]
            }
        ]
        metrics = parse_measure_metrics(measure_groups)
        
        assert len(metrics) == 1
        assert abs(metrics[0].value - 75.432) < 0.001
    
    def test_skip_unknown_measure_type(self):
        """Skip unknown measure types."""
        measure_groups = [
            {
                "date": 1705328400,
                "measures": [
                    {"type": 9999, "value": 100, "unit": 0}  # Unknown type
                ]
            }
        ]
        metrics = parse_measure_metrics(measure_groups)
        
        assert len(metrics) == 0
    
    def test_skip_missing_date(self):
        """Skip measure groups without date."""
        measure_groups = [
            {
                "measures": [
                    {"type": 1, "value": 75000, "unit": -3}
                ]
            }
        ]
        metrics = parse_measure_metrics(measure_groups)
        
        assert len(metrics) == 0


class TestParseSleepMetrics:
    """Tests for sleep metrics parsing."""
    
    def test_parse_sleep_hours(self):
        """Parse total sleep duration."""
        records = [
            {
                "date": "2024-01-15",
                "data": {
                    "total_sleep_time": 25200,  # 7 hours in seconds
                }
            }
        ]
        metrics = parse_sleep_metrics(records)
        
        sleep_hours = next(m for m in metrics if m.metric_name == "sleep_hours")
        assert sleep_hours.value == 7.0
        assert sleep_hours.source == "withings"
    
    def test_parse_sleep_stages(self):
        """Parse sleep stage durations."""
        records = [
            {
                "date": "2024-01-15",
                "data": {
                    "deepsleepduration": 5400,   # 1.5 hours
                    "lightsleepduration": 14400, # 4 hours
                    "remsleepduration": 5400,    # 1.5 hours
                }
            }
        ]
        metrics = parse_sleep_metrics(records)
        
        names = {m.metric_name for m in metrics}
        assert "deep_sleep_hours" in names
        assert "light_sleep_hours" in names
        assert "rem_sleep_hours" in names
        
        deep = next(m for m in metrics if m.metric_name == "deep_sleep_hours")
        assert deep.value == 1.5
    
    def test_parse_sleep_heart_rate(self):
        """Parse sleep heart rate metrics."""
        records = [
            {
                "date": "2024-01-15",
                "data": {
                    "hr_average": 58,
                    "hr_min": 52,
                    "hr_max": 72,
                }
            }
        ]
        metrics = parse_sleep_metrics(records)
        
        names = {m.metric_name for m in metrics}
        assert "sleep_hr_avg" in names
        assert "sleep_hr_min" in names
        assert "sleep_hr_max" in names
    
    def test_parse_wakeup_count(self):
        """Parse wakeup count."""
        records = [
            {
                "date": "2024-01-15",
                "data": {
                    "wakeupcount": 3,
                }
            }
        ]
        metrics = parse_sleep_metrics(records)
        
        wakeup = next(m for m in metrics if m.metric_name == "wakeup_count")
        assert wakeup.value == 3.0
    
    def test_parse_sleep_score(self):
        """Parse sleep score."""
        records = [
            {
                "date": "2024-01-15",
                "data": {
                    "sleep_score": 85,
                }
            }
        ]
        metrics = parse_sleep_metrics(records)
        
        score = next(m for m in metrics if m.metric_name == "sleep_score")
        assert score.value == 85.0
    
    def test_parse_breathing_and_snoring(self):
        """Parse breathing disturbances and snoring."""
        records = [
            {
                "date": "2024-01-15",
                "data": {
                    "breathing_disturbances_intensity": 15,
                    "snoring": 1800,  # 30 minutes in seconds
                }
            }
        ]
        metrics = parse_sleep_metrics(records)
        
        breathing = next(m for m in metrics if m.metric_name == "breathing_disturbances")
        assert breathing.value == 15.0
        
        snoring = next(m for m in metrics if m.metric_name == "snoring_minutes")
        assert snoring.value == 30.0
    
    def test_skip_missing_date(self):
        """Skip records without date."""
        records = [
            {
                "data": {
                    "total_sleep_time": 25200,
                }
            }
        ]
        metrics = parse_sleep_metrics(records)
        
        assert len(metrics) == 0


class TestGetSupportedMetrics:
    """Tests for get_supported_metrics."""
    
    def test_returns_sorted_list(self):
        """Returns sorted list of metric names."""
        metrics = get_supported_metrics()
        
        assert isinstance(metrics, list)
        assert metrics == sorted(metrics)
    
    def test_includes_measure_metrics(self):
        """Includes metrics from measures."""
        metrics = get_supported_metrics()
        
        assert "weight_kg" in metrics
        assert "systolic_bp" in metrics
        assert "diastolic_bp" in metrics
        assert "heart_rate" in metrics
    
    def test_includes_sleep_metrics(self):
        """Includes sleep metrics."""
        metrics = get_supported_metrics()
        
        assert "sleep_hours" in metrics
        assert "deep_sleep_hours" in metrics
        assert "rem_sleep_hours" in metrics
        assert "sleep_score" in metrics


class TestImportWithings:
    """Tests for import_withings function."""
    
    def test_import_requires_httpx(self, tmp_path):
        """Import raises ImportError when httpx not available."""
        from resonance.database import Database
        from resonance.ingest import withings
        
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        
        original_httpx = withings.httpx
        withings.httpx = None
        
        try:
            with pytest.raises(ImportError, match="httpx is required"):
                withings.import_withings(db)
        finally:
            withings.httpx = original_httpx
    
    def test_import_requires_credentials(self, tmp_path):
        """Import raises ValueError when no credentials available."""
        from resonance.database import Database
        from resonance.ingest import withings
        
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        
        creds_path = tmp_path / "nonexistent.json"
        
        with patch("resonance.ingest.withings.get_credentials_path", return_value=creds_path):
            with pytest.raises(ValueError, match="No saved Withings credentials"):
                withings.import_withings(db)
