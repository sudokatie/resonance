"""Data models for Resonance."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MetricRecord:
    """A single metric value for a specific date."""
    
    date: str  # YYYY-MM-DD
    metric_name: str
    value: float
    source: str  # 'apple_health', 'manual', etc.
    id: int | None = None  # Optional database row ID
    
    def __post_init__(self) -> None:
        """Validate date format."""
        if self.date and len(self.date) == 10:
            # Basic format check
            parts = self.date.split("-")
            if len(parts) != 3:
                raise ValueError(f"Invalid date format: {self.date}")


@dataclass
class PatternRecord:
    """A discovered correlation pattern."""
    
    metric1: str
    metric2: str
    correlation: float  # -1 to 1
    p_value: float
    lag_days: int  # 0 = same day, 1 = next day effect, etc.
    sample_size: int
    confidence: str  # 'low', 'medium', 'high', 'none'
    
    def __post_init__(self) -> None:
        """Validate confidence level."""
        valid_confidence = ('none', 'low', 'medium', 'high')
        if self.confidence not in valid_confidence:
            raise ValueError(f"confidence must be one of {valid_confidence}")


@dataclass
class EventRecord:
    """A manual event or log entry."""
    
    timestamp: str  # ISO 8601
    event_type: str  # 'mood', 'energy', 'note', etc.
    value: float | None = None
    note: str | None = None
    tags: list[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Ensure tags is a list."""
        if self.tags is None:
            self.tags = []


@dataclass
class HealthRecord:
    """A record from Apple Health export."""
    
    record_type: str  # HKQuantityTypeIdentifier...
    value: float
    unit: str
    start_date: datetime
    end_date: datetime
    
    @property
    def date(self) -> str:
        """Get the date as YYYY-MM-DD string."""
        return self.start_date.date().isoformat()
    
    @property
    def duration_hours(self) -> float:
        """Get duration in hours (useful for sleep)."""
        delta = self.end_date - self.start_date
        return delta.total_seconds() / 3600


def metric_record_from_dict(data: dict[str, Any]) -> MetricRecord:
    """Create MetricRecord from dictionary."""
    return MetricRecord(
        date=data["date"],
        metric_name=data["metric_name"],
        value=float(data["value"]),
        source=data["source"],
    )


def pattern_record_from_dict(data: dict[str, Any]) -> PatternRecord:
    """Create PatternRecord from dictionary."""
    return PatternRecord(
        metric1=data["metric1"],
        metric2=data["metric2"],
        correlation=float(data["correlation"]),
        p_value=float(data["p_value"]),
        lag_days=int(data["lag_days"]),
        sample_size=int(data["sample_size"]),
        confidence=data["confidence"],
    )


def event_record_from_dict(data: dict[str, Any]) -> EventRecord:
    """Create EventRecord from dictionary."""
    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return EventRecord(
        timestamp=data["timestamp"],
        event_type=data["event_type"],
        value=float(data["value"]) if data.get("value") is not None else None,
        note=data.get("note"),
        tags=tags,
    )
