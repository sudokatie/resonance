"""Tests for Google Fit integration."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from resonance.ingest.google_fit import (
    GoogleFitCredentials,
    aggregate_to_daily,
    get_credentials_path,
    get_supported_metrics,
    load_credentials,
    save_credentials,
    DATA_TYPE_MAP,
)


class TestGoogleFitCredentials:
    """Tests for GoogleFitCredentials."""
    
    def test_is_expired_false(self):
        """Not expired when time is before expiry."""
        creds = GoogleFitCredentials(
            access_token="test",
            refresh_token="test",
            expires_at=time.time() + 3600,
            client_id="id",
            client_secret="secret",
        )
        assert not creds.is_expired()
    
    def test_is_expired_true(self):
        """Expired when time is past expiry."""
        creds = GoogleFitCredentials(
            access_token="test",
            refresh_token="test",
            expires_at=time.time() - 60,
            client_id="id",
            client_secret="secret",
        )
        assert creds.is_expired()
    
    def test_is_expired_buffer(self):
        """Expired within 60 second buffer."""
        creds = GoogleFitCredentials(
            access_token="test",
            refresh_token="test",
            expires_at=time.time() + 30,  # 30 seconds from now
            client_id="id",
            client_secret="secret",
        )
        assert creds.is_expired()  # Within 60s buffer
    
    def test_to_dict(self):
        """Convert to dictionary."""
        creds = GoogleFitCredentials(
            access_token="access",
            refresh_token="refresh",
            expires_at=1234567890.0,
            client_id="client",
            client_secret="secret",
        )
        d = creds.to_dict()
        assert d["access_token"] == "access"
        assert d["refresh_token"] == "refresh"
        assert d["expires_at"] == 1234567890.0
        assert d["client_id"] == "client"
        assert d["client_secret"] == "secret"
    
    def test_from_dict(self):
        """Create from dictionary."""
        d = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": 1234567890.0,
            "client_id": "client",
            "client_secret": "secret",
        }
        creds = GoogleFitCredentials.from_dict(d)
        assert creds.access_token == "access"
        assert creds.refresh_token == "refresh"


class TestCredentialStorage:
    """Tests for credential storage."""
    
    def test_get_credentials_path(self):
        """Get path to credentials file."""
        path = get_credentials_path()
        assert path.name == "google_fit_credentials.json"
        assert ".config/resonance" in str(path)
    
    def test_save_and_load_credentials(self, tmp_path):
        """Save and load credentials."""
        creds = GoogleFitCredentials(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_at=time.time() + 3600,
            client_id="test_id",
            client_secret="test_secret",
        )
        
        # Mock the path
        creds_path = tmp_path / "creds.json"
        with patch("resonance.ingest.google_fit.get_credentials_path", return_value=creds_path):
            save_credentials(creds)
            loaded = load_credentials()
        
        assert loaded is not None
        assert loaded.access_token == "test_access"
        assert loaded.refresh_token == "test_refresh"
    
    def test_load_credentials_missing(self, tmp_path):
        """Load returns None when file missing."""
        creds_path = tmp_path / "nonexistent.json"
        with patch("resonance.ingest.google_fit.get_credentials_path", return_value=creds_path):
            loaded = load_credentials()
        assert loaded is None
    
    def test_load_credentials_invalid_json(self, tmp_path):
        """Load returns None for invalid JSON."""
        creds_path = tmp_path / "invalid.json"
        creds_path.write_text("not json")
        with patch("resonance.ingest.google_fit.get_credentials_path", return_value=creds_path):
            loaded = load_credentials()
        assert loaded is None


class TestAggregateToDailySleep:
    """Tests for daily aggregation."""
    
    def test_aggregate_steps(self):
        """Aggregate step count data."""
        now = datetime.now()
        today_ns = int(now.timestamp() * 1e9)
        
        data_points = [
            {
                "startTimeNanos": str(today_ns),
                "value": [{"intVal": 1000}],
            },
            {
                "startTimeNanos": str(today_ns + 3600_000_000_000),  # 1 hour later
                "value": [{"intVal": 500}],
            },
        ]
        
        result = aggregate_to_daily(data_points, "com.google.step_count.delta")
        today_str = now.date().isoformat()
        
        assert today_str in result
        assert result[today_str] == 1500  # sum
    
    def test_aggregate_heart_rate(self):
        """Aggregate heart rate data (average)."""
        now = datetime.now()
        today_ns = int(now.timestamp() * 1e9)
        
        data_points = [
            {
                "startTimeNanos": str(today_ns),
                "value": [{"fpVal": 70.0}],
            },
            {
                "startTimeNanos": str(today_ns + 3600_000_000_000),
                "value": [{"fpVal": 80.0}],
            },
        ]
        
        result = aggregate_to_daily(data_points, "com.google.heart_rate.bpm")
        today_str = now.date().isoformat()
        
        assert today_str in result
        assert result[today_str] == 75.0  # average
    
    def test_aggregate_weight(self):
        """Aggregate weight data (last value)."""
        now = datetime.now()
        today_ns = int(now.timestamp() * 1e9)
        
        data_points = [
            {
                "startTimeNanos": str(today_ns),
                "value": [{"fpVal": 70.0}],
            },
            {
                "startTimeNanos": str(today_ns + 3600_000_000_000),
                "value": [{"fpVal": 70.5}],
            },
        ]
        
        result = aggregate_to_daily(data_points, "com.google.weight")
        today_str = now.date().isoformat()
        
        assert today_str in result
        assert result[today_str] == 70.5  # last
    
    def test_aggregate_empty(self):
        """Empty data points return empty result."""
        result = aggregate_to_daily([], "com.google.step_count.delta")
        assert result == {}
    
    def test_aggregate_unknown_type(self):
        """Unknown data type returns empty result."""
        result = aggregate_to_daily([{"value": [{"intVal": 100}]}], "unknown.type")
        assert result == {}


class TestSupportedMetrics:
    """Tests for supported metrics."""
    
    def test_get_supported_metrics(self):
        """Get list of supported metrics."""
        metrics = get_supported_metrics()
        assert "steps" in metrics
        assert "sleep_hours" in metrics
        assert "heart_rate_avg" in metrics
        assert "weight_kg" in metrics
    
    def test_data_type_map_complete(self):
        """Data type map has required fields."""
        for data_type, (metric_name, agg_method) in DATA_TYPE_MAP.items():
            assert isinstance(data_type, str)
            assert isinstance(metric_name, str)
            assert agg_method in ("sum", "avg", "last")
