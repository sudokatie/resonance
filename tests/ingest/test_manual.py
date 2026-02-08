"""Tests for manual metric logging."""

import pytest
from datetime import date

from resonance.ingest.manual import (
    log_metric,
    log_event,
    parse_tags,
    normalize_metric_name,
    validate_metric_value,
)
from resonance.database import Database


@pytest.fixture
def db(temp_db):
    """Create a test database."""
    database = Database(temp_db)
    yield database
    database.close()


def test_log_mood_value(db):
    """Log a mood value."""
    log_metric(db, "mood", 7.0)
    metrics = db.get_metrics(name="mood")
    assert len(metrics) == 1
    assert metrics[0].value == 7.0
    assert metrics[0].source == "manual"


def test_log_energy_value(db):
    """Log an energy value."""
    log_metric(db, "energy", 8.0)
    metrics = db.get_metrics(name="energy")
    assert len(metrics) == 1
    assert metrics[0].value == 8.0


def test_log_custom_metric(db):
    """Log a custom metric name."""
    log_metric(db, "focus", 6.0)
    metrics = db.get_metrics(name="focus")
    assert len(metrics) == 1


def test_log_with_note_creates_event(db):
    """Logging with note creates an event."""
    log_metric(db, "mood", 7.0, note="Good day at work")
    events = db.get_events()
    assert len(events) == 1
    assert events[0].note == "Good day at work"


def test_log_with_tags_creates_event(db):
    """Logging with tags creates an event."""
    log_metric(db, "mood", 7.0, tags=["work", "productive"])
    events = db.get_events()
    assert len(events) == 1
    assert events[0].tags == ["work", "productive"]


def test_log_same_metric_twice_updates(db):
    """Logging same metric twice on same day updates value."""
    log_metric(db, "mood", 5.0)
    log_metric(db, "mood", 8.0)
    metrics = db.get_metrics(name="mood")
    assert len(metrics) == 1
    assert metrics[0].value == 8.0


def test_parse_tags_comma_separated():
    """Parse comma-separated tags."""
    tags = parse_tags("work, productive, morning")
    assert tags == ["work", "productive", "morning"]


def test_parse_tags_handles_whitespace():
    """Parse tags handles extra whitespace."""
    tags = parse_tags("  work ,  productive  ")
    assert tags == ["work", "productive"]


def test_parse_tags_empty():
    """Parse empty tag string."""
    assert parse_tags("") == []
    assert parse_tags(None) == []


def test_normalize_metric_name():
    """Normalize metric names."""
    assert normalize_metric_name("Mood") == "mood"
    assert normalize_metric_name("ENERGY") == "energy"
    assert normalize_metric_name("sleep quality") == "sleep_quality"
    assert normalize_metric_name("stress-level") == "stress_level"


def test_validate_mood_in_range():
    """Validate mood value in range."""
    valid, _ = validate_metric_value("mood", 7.0)
    assert valid


def test_validate_mood_out_of_range():
    """Validate mood value out of range."""
    valid, msg = validate_metric_value("mood", 15.0)
    assert not valid
    assert "between 1 and 10" in msg


def test_validate_negative_value():
    """Validate negative values rejected."""
    valid, msg = validate_metric_value("steps", -100.0)
    assert not valid
    assert "negative" in msg


def test_log_event_without_metric(db):
    """Log an event without creating a metric."""
    log_event(db, "note", note="Just a note")
    events = db.get_events()
    assert len(events) == 1
    assert events[0].event_type == "note"
    # Should not create a metric
    metrics = db.get_metrics()
    assert len(metrics) == 0
