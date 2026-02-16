"""Tests for Fitbit integration."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from resonance.ingest.fitbit import (
    FitbitCredentials,
    get_basic_auth,
    get_credentials_path,
    get_supported_metrics,
    load_credentials,
    parse_sleep_data,
    parse_time_series,
    save_credentials,
    ENDPOINTS,
)


class TestFitbitCredentials:
    """Tests for FitbitCredentials."""
    
    def test_is_expired_false(self):
        """Not expired when time is before expiry."""
        creds = FitbitCredentials(
            access_token="test",
            refresh_token="test",
            expires_at=time.time() + 3600,
            client_id="id",
            client_secret="secret",
        )
        assert not creds.is_expired()
    
    def test_is_expired_true(self):
        """Expired when time is past expiry."""
        creds = FitbitCredentials(
            access_token="test",
            refresh_token="test",
            expires_at=time.time() - 60,
            client_id="id",
            client_secret="secret",
        )
        assert creds.is_expired()
    
    def test_to_dict(self):
        """Convert to dictionary."""
        creds = FitbitCredentials(
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
    
    def test_from_dict(self):
        """Create from dictionary."""
        d = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": 1234567890.0,
            "client_id": "client",
            "client_secret": "secret",
        }
        creds = FitbitCredentials.from_dict(d)
        assert creds.access_token == "access"
        assert creds.client_id == "client"


class TestBasicAuth:
    """Tests for basic auth header."""
    
    def test_get_basic_auth(self):
        """Generate basic auth header."""
        auth = get_basic_auth("client_id", "client_secret")
        assert auth.startswith("Basic ")
        # Decode and verify
        import base64
        encoded = auth.split(" ")[1]
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "client_id:client_secret"


class TestCredentialStorage:
    """Tests for credential storage."""
    
    def test_get_credentials_path(self):
        """Get path to credentials file."""
        path = get_credentials_path()
        assert path.name == "fitbit_credentials.json"
        assert ".config/resonance" in str(path)
    
    def test_save_and_load_credentials(self, tmp_path):
        """Save and load credentials."""
        creds = FitbitCredentials(
            access_token="test_access",
            refresh_token="test_refresh",
            expires_at=time.time() + 3600,
            client_id="test_id",
            client_secret="test_secret",
        )
        
        creds_path = tmp_path / "creds.json"
        with patch("resonance.ingest.fitbit.get_credentials_path", return_value=creds_path):
            save_credentials(creds)
            loaded = load_credentials()
        
        assert loaded is not None
        assert loaded.access_token == "test_access"
    
    def test_load_credentials_missing(self, tmp_path):
        """Load returns None when file missing."""
        creds_path = tmp_path / "nonexistent.json"
        with patch("resonance.ingest.fitbit.get_credentials_path", return_value=creds_path):
            loaded = load_credentials()
        assert loaded is None


class TestParseTimeSeries:
    """Tests for time series parsing."""
    
    def test_parse_steps(self):
        """Parse steps time series."""
        data = {
            "activities-steps": [
                {"dateTime": "2024-01-15", "value": "10000"},
                {"dateTime": "2024-01-16", "value": "8000"},
            ]
        }
        result = parse_time_series(data, "activities-steps", "steps")
        assert len(result) == 2
        assert result[0] == ("2024-01-15", 10000.0)
        assert result[1] == ("2024-01-16", 8000.0)
    
    def test_parse_empty_data(self):
        """Parse empty data."""
        data = {"activities-steps": []}
        result = parse_time_series(data, "activities-steps", "steps")
        assert result == []
    
    def test_parse_missing_key(self):
        """Parse when key is missing."""
        data = {}
        result = parse_time_series(data, "activities-steps", "steps")
        assert result == []
    
    def test_parse_invalid_value(self):
        """Skip items with invalid values."""
        data = {
            "activities-steps": [
                {"dateTime": "2024-01-15", "value": "invalid"},
                {"dateTime": "2024-01-16", "value": "8000"},
            ]
        }
        result = parse_time_series(data, "activities-steps", "steps")
        assert len(result) == 1
        assert result[0] == ("2024-01-16", 8000.0)


class TestParseSleepData:
    """Tests for sleep data parsing."""
    
    def test_parse_sleep(self):
        """Parse sleep data."""
        data = {
            "sleep": [
                {
                    "dateOfSleep": "2024-01-15",
                    "minutesAsleep": 420,
                },
                {
                    "dateOfSleep": "2024-01-16",
                    "minutesAsleep": 480,
                },
            ]
        }
        result = parse_sleep_data(data)
        assert len(result) == 2
        assert result[0] == ("2024-01-15", 7.0)  # 420 min = 7 hours
        assert result[1] == ("2024-01-16", 8.0)  # 480 min = 8 hours
    
    def test_parse_sleep_empty(self):
        """Parse empty sleep data."""
        data = {"sleep": []}
        result = parse_sleep_data(data)
        assert result == []
    
    def test_parse_sleep_zero_minutes(self):
        """Skip sleep entries with zero minutes."""
        data = {
            "sleep": [
                {"dateOfSleep": "2024-01-15", "minutesAsleep": 0},
                {"dateOfSleep": "2024-01-16", "minutesAsleep": 420},
            ]
        }
        result = parse_sleep_data(data)
        assert len(result) == 1
        assert result[0] == ("2024-01-16", 7.0)


class TestSupportedMetrics:
    """Tests for supported metrics."""
    
    def test_get_supported_metrics(self):
        """Get list of supported metrics."""
        metrics = get_supported_metrics()
        assert "steps" in metrics
        assert "sleep_hours" in metrics
        assert "heart_rate_avg" in metrics
    
    def test_endpoints_complete(self):
        """Endpoints have required fields."""
        for endpoint, json_key, metric_name, agg in ENDPOINTS:
            assert isinstance(endpoint, str)
            assert "{" in endpoint  # Has format placeholders
            assert isinstance(json_key, str)
            assert isinstance(metric_name, str)
            assert agg in ("sum", "avg", "last")
