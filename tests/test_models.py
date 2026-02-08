"""Tests for data models."""

import pytest
from datetime import datetime

from resonance.models import (
    MetricRecord,
    PatternRecord,
    EventRecord,
    HealthRecord,
    metric_record_from_dict,
    event_record_from_dict,
)


def test_create_metric_record():
    """Create a valid MetricRecord."""
    record = MetricRecord(
        date="2024-01-15",
        metric_name="steps",
        value=8500.0,
        source="apple_health",
    )
    assert record.date == "2024-01-15"
    assert record.metric_name == "steps"
    assert record.value == 8500.0
    assert record.source == "apple_health"


def test_create_pattern_record():
    """Create a valid PatternRecord."""
    record = PatternRecord(
        metric1="sleep_hours",
        metric2="mood",
        correlation=0.72,
        p_value=0.001,
        lag_days=1,
        sample_size=50,
        confidence="high",
    )
    assert record.metric1 == "sleep_hours"
    assert record.metric2 == "mood"
    assert record.correlation == 0.72
    assert record.confidence == "high"


def test_pattern_record_invalid_confidence():
    """PatternRecord rejects invalid confidence."""
    with pytest.raises(ValueError):
        PatternRecord(
            metric1="a",
            metric2="b",
            correlation=0.5,
            p_value=0.01,
            lag_days=0,
            sample_size=30,
            confidence="invalid",
        )


def test_create_event_record_with_value():
    """Create EventRecord with a value."""
    record = EventRecord(
        timestamp="2024-01-15T14:30:00",
        event_type="mood",
        value=7.0,
        note="Good day",
        tags=["work", "productive"],
    )
    assert record.value == 7.0
    assert record.note == "Good day"
    assert record.tags == ["work", "productive"]


def test_create_event_record_without_value():
    """Create EventRecord without a value."""
    record = EventRecord(
        timestamp="2024-01-15T14:30:00",
        event_type="note",
        value=None,
        note="Just a note",
    )
    assert record.value is None
    assert record.tags == []


def test_event_record_tags_defaults_to_list():
    """EventRecord tags defaults to empty list."""
    record = EventRecord(
        timestamp="2024-01-15T14:30:00",
        event_type="mood",
    )
    assert record.tags == []


def test_create_health_record():
    """Create a valid HealthRecord."""
    record = HealthRecord(
        record_type="HKQuantityTypeIdentifierStepCount",
        value=1500.0,
        unit="count",
        start_date=datetime(2024, 1, 15, 10, 0, 0),
        end_date=datetime(2024, 1, 15, 10, 30, 0),
    )
    assert record.record_type == "HKQuantityTypeIdentifierStepCount"
    assert record.value == 1500.0
    assert record.date == "2024-01-15"


def test_health_record_duration():
    """HealthRecord calculates duration correctly."""
    record = HealthRecord(
        record_type="HKCategoryTypeIdentifierSleepAnalysis",
        value=1.0,
        unit="",
        start_date=datetime(2024, 1, 15, 22, 0, 0),
        end_date=datetime(2024, 1, 16, 6, 0, 0),
    )
    assert record.duration_hours == 8.0


def test_metric_record_from_dict():
    """Create MetricRecord from dictionary."""
    data = {
        "date": "2024-01-15",
        "metric_name": "steps",
        "value": "8500",  # String should be converted
        "source": "apple_health",
    }
    record = metric_record_from_dict(data)
    assert record.value == 8500.0


def test_event_record_from_dict_with_string_tags():
    """Create EventRecord from dict with comma-separated tags."""
    data = {
        "timestamp": "2024-01-15T14:30:00",
        "event_type": "mood",
        "value": 7,
        "tags": "work, productive, morning",
    }
    record = event_record_from_dict(data)
    assert record.tags == ["work", "productive", "morning"]
