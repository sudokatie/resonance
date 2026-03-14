"""Anomaly detection and alerts for health metrics.

Detects when metrics deviate from personal baselines and generates alerts.
Integrates with external notification systems via CLI output or JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional, TYPE_CHECKING
import json
import statistics
from pathlib import Path

if TYPE_CHECKING:
    from ..database import Database


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of anomalies detected."""
    HIGH = "high"          # Above normal range
    LOW = "low"            # Below normal range
    MISSING = "missing"    # No data when expected
    SUDDEN_CHANGE = "sudden_change"  # Large day-over-day change


@dataclass
class MetricRange:
    """Normal range for a metric."""
    metric_name: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    expected_daily: bool = True  # Whether data is expected daily
    
    def is_in_range(self, value: float) -> bool:
        """Check if value is within normal range."""
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        return True
    
    def get_deviation(self, value: float) -> tuple[AlertType, float]:
        """Get deviation type and amount.
        
        Returns:
            Tuple of (AlertType, deviation_amount)
        """
        if self.min_value is not None and value < self.min_value:
            return (AlertType.LOW, self.min_value - value)
        if self.max_value is not None and value > self.max_value:
            return (AlertType.HIGH, value - self.max_value)
        return (AlertType.HIGH, 0)  # In range


@dataclass
class Alert:
    """An anomaly alert."""
    metric_name: str
    alert_type: AlertType
    severity: AlertSeverity
    current_value: float
    expected_range: tuple[Optional[float], Optional[float]]
    message: str
    detected_at: datetime = field(default_factory=datetime.now)
    suppressed: bool = False
    suppression_reason: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "metric": self.metric_name,
            "type": self.alert_type.value,
            "severity": self.severity.value,
            "value": self.current_value,
            "range": [self.expected_range[0], self.expected_range[1]],
            "message": self.message,
            "time": self.detected_at.isoformat(),
            "suppressed": self.suppressed,
        }


@dataclass
class AlertConfig:
    """Configuration for alert detection."""
    # Number of days for baseline calculation
    baseline_days: int = 30
    # Minimum samples needed for baseline
    min_samples: int = 7
    # Number of standard deviations for warning
    warning_threshold: float = 2.0
    # Number of standard deviations for critical
    critical_threshold: float = 3.0
    # Percentage change for sudden change detection
    sudden_change_percent: float = 30.0
    # Hours to suppress duplicate alerts
    suppression_hours: int = 24


class AnomalyDetector:
    """Detects anomalies in health metrics."""
    
    def __init__(
        self,
        db: "Database",
        config: Optional[AlertConfig] = None,
        ranges_file: Optional[Path] = None,
    ):
        """Initialize detector.
        
        Args:
            db: Database instance
            config: Alert configuration
            ranges_file: Optional JSON file with custom ranges
        """
        self.db = db
        self.config = config or AlertConfig()
        self.ranges: dict[str, MetricRange] = {}
        self.recent_alerts: list[Alert] = []
        
        # Load custom ranges if provided
        if ranges_file and ranges_file.exists():
            self._load_ranges(ranges_file)
    
    def _load_ranges(self, path: Path) -> None:
        """Load custom metric ranges from JSON file."""
        try:
            data = json.loads(path.read_text())
            for name, values in data.items():
                self.ranges[name] = MetricRange(
                    metric_name=name,
                    min_value=values.get("min"),
                    max_value=values.get("max"),
                    expected_daily=values.get("expected_daily", True),
                )
        except (json.JSONDecodeError, KeyError):
            pass
    
    def set_range(
        self,
        metric_name: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        expected_daily: bool = True,
    ) -> None:
        """Set normal range for a metric.
        
        Args:
            metric_name: Name of the metric
            min_value: Minimum acceptable value
            max_value: Maximum acceptable value
            expected_daily: Whether data is expected daily
        """
        self.ranges[metric_name] = MetricRange(
            metric_name=metric_name,
            min_value=min_value,
            max_value=max_value,
            expected_daily=expected_daily,
        )
    
    def _get_values_in_range(
        self,
        metric_name: str,
        start_date: str,
        end_date: str,
    ) -> list[float]:
        """Get metric values in a date range.
        
        Args:
            metric_name: Name of the metric
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of values
        """
        records = self.db.get_metrics(
            name=metric_name,
            from_date=start_date,
            to_date=end_date,
        )
        return [r.value for r in records]
    
    def calculate_baseline(self, metric_name: str) -> Optional[tuple[float, float]]:
        """Calculate baseline mean and std dev for a metric.
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Tuple of (mean, std_dev) or None if insufficient data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=self.config.baseline_days)
        
        values = self._get_values_in_range(
            metric_name,
            start_date.isoformat(),
            end_date.isoformat(),
        )
        
        if len(values) < self.config.min_samples:
            return None
        
        mean = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0
        
        # Apply minimum std dev to avoid false positives on stable metrics
        if std_dev < 0.01 * mean:
            std_dev = 0.01 * mean
        
        return (mean, std_dev)
    
    def detect_anomaly(
        self,
        metric_name: str,
        value: float,
        check_date: Optional[date] = None,
    ) -> Optional[Alert]:
        """Detect if a value is anomalous.
        
        Args:
            metric_name: Name of the metric
            value: Current value
            check_date: Date of the value (defaults to today)
            
        Returns:
            Alert if anomaly detected, None otherwise
        """
        if check_date is None:
            check_date = date.today()
        
        # Check custom range first
        if metric_name in self.ranges:
            range_def = self.ranges[metric_name]
            if not range_def.is_in_range(value):
                alert_type, deviation = range_def.get_deviation(value)
                severity = AlertSeverity.WARNING
                
                # Critical if way outside range
                if range_def.min_value and value < range_def.min_value * 0.5:
                    severity = AlertSeverity.CRITICAL
                if range_def.max_value and value > range_def.max_value * 1.5:
                    severity = AlertSeverity.CRITICAL
                
                return self._create_alert(
                    metric_name=metric_name,
                    alert_type=alert_type,
                    severity=severity,
                    value=value,
                    expected_range=(range_def.min_value, range_def.max_value),
                )
        
        # Fall back to statistical baseline
        baseline = self.calculate_baseline(metric_name)
        if baseline is None:
            return None
        
        mean, std_dev = baseline
        deviation = (value - mean) / std_dev if std_dev > 0 else 0
        
        if abs(deviation) >= self.config.critical_threshold:
            severity = AlertSeverity.CRITICAL
        elif abs(deviation) >= self.config.warning_threshold:
            severity = AlertSeverity.WARNING
        else:
            return None  # Within normal range
        
        alert_type = AlertType.HIGH if deviation > 0 else AlertType.LOW
        
        # Calculate expected range
        low = mean - (self.config.warning_threshold * std_dev)
        high = mean + (self.config.warning_threshold * std_dev)
        
        return self._create_alert(
            metric_name=metric_name,
            alert_type=alert_type,
            severity=severity,
            value=value,
            expected_range=(low, high),
        )
    
    def detect_sudden_change(
        self,
        metric_name: str,
        today_value: float,
        yesterday_value: float,
    ) -> Optional[Alert]:
        """Detect sudden day-over-day change.
        
        Args:
            metric_name: Name of the metric
            today_value: Today's value
            yesterday_value: Yesterday's value
            
        Returns:
            Alert if sudden change detected, None otherwise
        """
        if yesterday_value == 0:
            return None
        
        pct_change = abs((today_value - yesterday_value) / yesterday_value) * 100
        
        if pct_change < self.config.sudden_change_percent:
            return None
        
        severity = AlertSeverity.WARNING
        if pct_change > self.config.sudden_change_percent * 2:
            severity = AlertSeverity.CRITICAL
        
        direction = "increased" if today_value > yesterday_value else "decreased"
        
        return Alert(
            metric_name=metric_name,
            alert_type=AlertType.SUDDEN_CHANGE,
            severity=severity,
            current_value=today_value,
            expected_range=(yesterday_value * 0.7, yesterday_value * 1.3),
            message=f"{metric_name} {direction} by {pct_change:.0f}% "
                    f"(from {yesterday_value:.1f} to {today_value:.1f})",
        )
    
    def detect_missing_data(
        self,
        metric_name: str,
        check_date: Optional[date] = None,
    ) -> Optional[Alert]:
        """Detect missing expected data.
        
        Args:
            metric_name: Name of the metric
            check_date: Date to check (defaults to yesterday)
            
        Returns:
            Alert if data is missing and expected, None otherwise
        """
        if check_date is None:
            check_date = date.today() - timedelta(days=1)
        
        # Check if we expect daily data for this metric
        if metric_name in self.ranges:
            if not self.ranges[metric_name].expected_daily:
                return None
        
        # Check if data exists
        values = self._get_values_in_range(
            metric_name,
            check_date.isoformat(),
            check_date.isoformat(),
        )
        
        if values:
            return None  # Data exists
        
        # Check if metric usually has data (>80% of last 30 days)
        end = date.today()
        start = end - timedelta(days=30)
        historical = self._get_values_in_range(
            metric_name,
            start.isoformat(),
            end.isoformat(),
        )
        
        if len(historical) < 24:  # Less than 80% coverage
            return None  # Metric doesn't have consistent data
        
        return Alert(
            metric_name=metric_name,
            alert_type=AlertType.MISSING,
            severity=AlertSeverity.INFO,
            current_value=0,
            expected_range=(None, None),
            message=f"No {metric_name} data recorded for {check_date.isoformat()}",
        )
    
    def _create_alert(
        self,
        metric_name: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        value: float,
        expected_range: tuple[Optional[float], Optional[float]],
    ) -> Alert:
        """Create an alert with appropriate message."""
        if alert_type == AlertType.HIGH:
            msg = f"{metric_name} is high: {value:.1f}"
            if expected_range[1]:
                msg += f" (expected max {expected_range[1]:.1f})"
        elif alert_type == AlertType.LOW:
            msg = f"{metric_name} is low: {value:.1f}"
            if expected_range[0]:
                msg += f" (expected min {expected_range[0]:.1f})"
        else:
            msg = f"{metric_name}: {value:.1f}"
        
        return Alert(
            metric_name=metric_name,
            alert_type=alert_type,
            severity=severity,
            current_value=value,
            expected_range=expected_range,
            message=msg,
        )
    
    def should_suppress(self, alert: Alert) -> tuple[bool, str]:
        """Check if alert should be suppressed.
        
        Args:
            alert: Alert to check
            
        Returns:
            Tuple of (should_suppress, reason)
        """
        cutoff = datetime.now() - timedelta(hours=self.config.suppression_hours)
        
        for recent in self.recent_alerts:
            if recent.detected_at < cutoff:
                continue
            
            # Same metric and type
            if (recent.metric_name == alert.metric_name and
                recent.alert_type == alert.alert_type and
                not recent.suppressed):
                return (True, f"Duplicate of alert from {recent.detected_at}")
        
        return (False, "")
    
    def check_all_metrics(self, target_date: Optional[date] = None) -> list[Alert]:
        """Check all tracked metrics for anomalies.
        
        Args:
            target_date: Date to check (defaults to today)
            
        Returns:
            List of detected alerts
        """
        if target_date is None:
            target_date = date.today()
        
        alerts = []
        yesterday = target_date - timedelta(days=1)
        
        # Get all metrics
        metric_names = self.db.get_metric_names()
        
        for metric_name in metric_names:
            # Get today's value
            today_values = self._get_values_in_range(
                metric_name,
                target_date.isoformat(),
                target_date.isoformat(),
            )
            
            if not today_values:
                # Check for missing data
                missing_alert = self.detect_missing_data(metric_name, target_date)
                if missing_alert:
                    alerts.append(missing_alert)
                continue
            
            today_value = today_values[0]  # Use first value
            
            # Check for anomaly
            anomaly = self.detect_anomaly(metric_name, today_value, target_date)
            if anomaly:
                # Check suppression
                suppress, reason = self.should_suppress(anomaly)
                if suppress:
                    anomaly.suppressed = True
                    anomaly.suppression_reason = reason
                alerts.append(anomaly)
            
            # Check for sudden change
            yesterday_values = self._get_values_in_range(
                metric_name,
                yesterday.isoformat(),
                yesterday.isoformat(),
            )
            
            if yesterday_values:
                change_alert = self.detect_sudden_change(
                    metric_name,
                    today_value,
                    yesterday_values[0],
                )
                if change_alert:
                    suppress, reason = self.should_suppress(change_alert)
                    if suppress:
                        change_alert.suppressed = True
                        change_alert.suppression_reason = reason
                    alerts.append(change_alert)
        
        # Update recent alerts
        self.recent_alerts.extend([a for a in alerts if not a.suppressed])
        
        return alerts


def format_alerts(alerts: list[Alert], include_suppressed: bool = False) -> str:
    """Format alerts as text.
    
    Args:
        alerts: List of alerts
        include_suppressed: Whether to include suppressed alerts
        
    Returns:
        Formatted string
    """
    if include_suppressed:
        filtered = alerts
    else:
        filtered = [a for a in alerts if not a.suppressed]
    
    if not filtered:
        return "No alerts."
    
    lines = ["Health Metric Alerts", "=" * 30, ""]
    
    # Group by severity
    critical = [a for a in filtered if a.severity == AlertSeverity.CRITICAL]
    warning = [a for a in filtered if a.severity == AlertSeverity.WARNING]
    info = [a for a in filtered if a.severity == AlertSeverity.INFO]
    
    if critical:
        lines.append("CRITICAL:")
        for a in critical:
            lines.append(f"  ! {a.message}")
        lines.append("")
    
    if warning:
        lines.append("WARNING:")
        for a in warning:
            lines.append(f"  * {a.message}")
        lines.append("")
    
    if info:
        lines.append("INFO:")
        for a in info:
            lines.append(f"  - {a.message}")
    
    return "\n".join(lines)


def alerts_to_json(alerts: list[Alert]) -> str:
    """Convert alerts to JSON.
    
    Args:
        alerts: List of alerts
        
    Returns:
        JSON string
    """
    return json.dumps([a.to_dict() for a in alerts], indent=2)
