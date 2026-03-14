"""Tests for anomaly detection and alerts."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock

from resonance.analysis.alerts import (
    MetricRange,
    Alert,
    AlertType,
    AlertSeverity,
    AlertConfig,
    AnomalyDetector,
    format_alerts,
    alerts_to_json,
)
from resonance.models import MetricRecord


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = MagicMock()
    db.get_metric_names.return_value = ["heart_rate", "sleep_hours", "steps"]
    return db


@pytest.fixture
def detector(mock_db):
    """Create an anomaly detector with mock db."""
    return AnomalyDetector(mock_db)


class TestMetricRange:
    """Tests for MetricRange."""
    
    def test_in_range(self):
        """Value within range should return True."""
        r = MetricRange("test", min_value=60, max_value=100)
        assert r.is_in_range(80) is True
    
    def test_below_range(self):
        """Value below min should return False."""
        r = MetricRange("test", min_value=60, max_value=100)
        assert r.is_in_range(50) is False
    
    def test_above_range(self):
        """Value above max should return False."""
        r = MetricRange("test", min_value=60, max_value=100)
        assert r.is_in_range(110) is False
    
    def test_no_min(self):
        """No minimum should allow any low value."""
        r = MetricRange("test", max_value=100)
        assert r.is_in_range(0) is True
        assert r.is_in_range(110) is False
    
    def test_no_max(self):
        """No maximum should allow any high value."""
        r = MetricRange("test", min_value=60)
        assert r.is_in_range(50) is False
        assert r.is_in_range(1000) is True
    
    def test_get_deviation_low(self):
        """Get deviation for low value."""
        r = MetricRange("test", min_value=60, max_value=100)
        alert_type, deviation = r.get_deviation(50)
        assert alert_type == AlertType.LOW
        assert deviation == 10
    
    def test_get_deviation_high(self):
        """Get deviation for high value."""
        r = MetricRange("test", min_value=60, max_value=100)
        alert_type, deviation = r.get_deviation(120)
        assert alert_type == AlertType.HIGH
        assert deviation == 20


class TestAlert:
    """Tests for Alert dataclass."""
    
    def test_create_alert(self):
        """Create a basic alert."""
        alert = Alert(
            metric_name="heart_rate",
            alert_type=AlertType.HIGH,
            severity=AlertSeverity.WARNING,
            current_value=120,
            expected_range=(60, 100),
            message="Heart rate is high",
        )
        assert alert.metric_name == "heart_rate"
        assert alert.suppressed is False
    
    def test_to_dict(self):
        """Convert alert to dictionary."""
        alert = Alert(
            metric_name="heart_rate",
            alert_type=AlertType.HIGH,
            severity=AlertSeverity.WARNING,
            current_value=120,
            expected_range=(60, 100),
            message="Heart rate is high",
        )
        d = alert.to_dict()
        
        assert d["metric"] == "heart_rate"
        assert d["type"] == "high"
        assert d["severity"] == "warning"
        assert d["value"] == 120


class TestAlertConfig:
    """Tests for AlertConfig."""
    
    def test_default_config(self):
        """Default config should have reasonable values."""
        cfg = AlertConfig()
        
        assert cfg.baseline_days > 0
        assert cfg.min_samples > 0
        assert cfg.warning_threshold > 0
        assert cfg.critical_threshold > cfg.warning_threshold


class TestAnomalyDetector:
    """Tests for AnomalyDetector."""
    
    def test_set_range(self, detector):
        """Set custom range for metric."""
        detector.set_range("heart_rate", min_value=60, max_value=100)
        
        assert "heart_rate" in detector.ranges
        assert detector.ranges["heart_rate"].min_value == 60
        assert detector.ranges["heart_rate"].max_value == 100
    
    def test_detect_anomaly_with_custom_range(self, detector, mock_db):
        """Detect anomaly using custom range."""
        detector.set_range("heart_rate", min_value=60, max_value=100)
        
        # Value above range
        alert = detector.detect_anomaly("heart_rate", 120)
        
        assert alert is not None
        assert alert.alert_type == AlertType.HIGH
        assert alert.severity == AlertSeverity.WARNING
    
    def test_detect_anomaly_critical(self, detector, mock_db):
        """Critical severity for extreme values."""
        detector.set_range("heart_rate", min_value=60, max_value=100)
        
        # Value way above range (>1.5x max)
        alert = detector.detect_anomaly("heart_rate", 160)
        
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
    
    def test_detect_no_anomaly(self, detector, mock_db):
        """No anomaly for normal value."""
        detector.set_range("heart_rate", min_value=60, max_value=100)
        
        alert = detector.detect_anomaly("heart_rate", 75)
        assert alert is None
    
    def test_calculate_baseline(self, detector, mock_db):
        """Calculate baseline from historical data."""
        # Mock return values
        records = [
            MetricRecord(date="2026-03-01", metric_name="heart_rate", value=70, source="test"),
            MetricRecord(date="2026-03-02", metric_name="heart_rate", value=72, source="test"),
            MetricRecord(date="2026-03-03", metric_name="heart_rate", value=68, source="test"),
            MetricRecord(date="2026-03-04", metric_name="heart_rate", value=71, source="test"),
            MetricRecord(date="2026-03-05", metric_name="heart_rate", value=69, source="test"),
            MetricRecord(date="2026-03-06", metric_name="heart_rate", value=73, source="test"),
            MetricRecord(date="2026-03-07", metric_name="heart_rate", value=70, source="test"),
        ]
        mock_db.get_metrics.return_value = records
        
        baseline = detector.calculate_baseline("heart_rate")
        
        assert baseline is not None
        mean, std_dev = baseline
        assert 69 <= mean <= 72
        assert std_dev > 0
    
    def test_calculate_baseline_insufficient_data(self, detector, mock_db):
        """Return None with insufficient data."""
        mock_db.get_metrics.return_value = [
            MetricRecord(date="2026-03-01", metric_name="heart_rate", value=70, source="test"),
        ]
        
        baseline = detector.calculate_baseline("heart_rate")
        assert baseline is None
    
    def test_detect_sudden_change(self, detector):
        """Detect sudden day-over-day change."""
        alert = detector.detect_sudden_change("steps", 15000, 5000)
        
        assert alert is not None
        assert alert.alert_type == AlertType.SUDDEN_CHANGE
        assert "increased" in alert.message
    
    def test_detect_sudden_change_decrease(self, detector):
        """Detect sudden decrease."""
        alert = detector.detect_sudden_change("steps", 3000, 10000)
        
        assert alert is not None
        assert "decreased" in alert.message
    
    def test_no_sudden_change(self, detector):
        """No alert for normal variation."""
        alert = detector.detect_sudden_change("steps", 10500, 10000)
        assert alert is None
    
    def test_should_suppress_duplicate(self, detector):
        """Suppress duplicate alerts."""
        alert1 = Alert(
            metric_name="heart_rate",
            alert_type=AlertType.HIGH,
            severity=AlertSeverity.WARNING,
            current_value=120,
            expected_range=(60, 100),
            message="Heart rate is high",
            detected_at=datetime.now(),
        )
        detector.recent_alerts.append(alert1)
        
        alert2 = Alert(
            metric_name="heart_rate",
            alert_type=AlertType.HIGH,
            severity=AlertSeverity.WARNING,
            current_value=125,
            expected_range=(60, 100),
            message="Heart rate is high",
        )
        
        suppress, reason = detector.should_suppress(alert2)
        assert suppress is True
        assert "Duplicate" in reason
    
    def test_no_suppress_different_metric(self, detector):
        """Don't suppress different metrics."""
        alert1 = Alert(
            metric_name="heart_rate",
            alert_type=AlertType.HIGH,
            severity=AlertSeverity.WARNING,
            current_value=120,
            expected_range=(60, 100),
            message="Heart rate is high",
        )
        detector.recent_alerts.append(alert1)
        
        alert2 = Alert(
            metric_name="blood_pressure",
            alert_type=AlertType.HIGH,
            severity=AlertSeverity.WARNING,
            current_value=150,
            expected_range=(90, 120),
            message="Blood pressure is high",
        )
        
        suppress, _ = detector.should_suppress(alert2)
        assert suppress is False


class TestFormatAlerts:
    """Tests for alert formatting."""
    
    def test_format_empty(self):
        """Format empty alert list."""
        output = format_alerts([])
        assert "No alerts" in output
    
    def test_format_with_alerts(self):
        """Format list with alerts."""
        alerts = [
            Alert(
                metric_name="heart_rate",
                alert_type=AlertType.HIGH,
                severity=AlertSeverity.CRITICAL,
                current_value=150,
                expected_range=(60, 100),
                message="Heart rate is high: 150",
            ),
            Alert(
                metric_name="steps",
                alert_type=AlertType.LOW,
                severity=AlertSeverity.WARNING,
                current_value=1000,
                expected_range=(5000, None),
                message="Steps is low: 1000",
            ),
        ]
        
        output = format_alerts(alerts)
        
        assert "CRITICAL" in output
        assert "WARNING" in output
        assert "heart_rate" in output or "Heart rate" in output
    
    def test_format_excludes_suppressed(self):
        """Suppressed alerts excluded by default."""
        alerts = [
            Alert(
                metric_name="heart_rate",
                alert_type=AlertType.HIGH,
                severity=AlertSeverity.WARNING,
                current_value=120,
                expected_range=(60, 100),
                message="Heart rate is high",
                suppressed=True,
            ),
        ]
        
        output = format_alerts(alerts)
        assert "No alerts" in output


class TestAlertsToJson:
    """Tests for JSON output."""
    
    def test_alerts_to_json(self):
        """Convert alerts to JSON."""
        alerts = [
            Alert(
                metric_name="test",
                alert_type=AlertType.HIGH,
                severity=AlertSeverity.WARNING,
                current_value=100,
                expected_range=(0, 50),
                message="Test alert",
            ),
        ]
        
        json_str = alerts_to_json(alerts)
        
        assert '"metric": "test"' in json_str
        assert '"type": "high"' in json_str
        assert '"severity": "warning"' in json_str
