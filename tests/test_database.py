"""Tests for database operations."""

import pytest
from pathlib import Path

from resonance.database import Database
from resonance.models import MetricRecord, PatternRecord, EventRecord


@pytest.fixture
def db(temp_db):
    """Create a test database."""
    database = Database(temp_db)
    yield database
    database.close()


def test_init_creates_database_file(temp_dir):
    """Database file is created on init."""
    db_path = temp_dir / "test.db"
    db = Database(db_path)
    assert db_path.exists()
    db.close()


def test_init_creates_parent_directories(temp_dir):
    """Parent directories are created if needed."""
    db_path = temp_dir / "subdir" / "nested" / "test.db"
    db = Database(db_path)
    assert db_path.exists()
    db.close()


def test_init_schema_creates_tables(db):
    """Schema initialization creates all required tables."""
    cursor = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {row[0] for row in cursor}
    assert "metrics" in tables
    assert "patterns" in tables
    assert "events" in tables


def test_insert_single_metric(db):
    """Insert a single metric value."""
    db.insert_metric("2024-01-15", "steps", 8500.0, "apple_health")
    metrics = db.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].value == 8500.0


def test_insert_duplicate_replaces(db):
    """Inserting duplicate date+metric replaces the value."""
    db.insert_metric("2024-01-15", "steps", 8500.0, "apple_health")
    db.insert_metric("2024-01-15", "steps", 9000.0, "apple_health")
    metrics = db.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].value == 9000.0


def test_bulk_insert_metrics(db):
    """Bulk insert multiple metrics."""
    records = [
        MetricRecord("2024-01-15", "steps", 8500.0, "apple_health"),
        MetricRecord("2024-01-15", "sleep_hours", 7.5, "apple_health"),
        MetricRecord("2024-01-16", "steps", 10000.0, "apple_health"),
    ]
    count = db.insert_metrics(records)
    assert count == 3
    assert len(db.get_metrics()) == 3


def test_bulk_insert_empty_list(db):
    """Bulk insert with empty list returns 0."""
    count = db.insert_metrics([])
    assert count == 0


def test_query_all_metrics(db):
    """Query all metrics without filters."""
    db.insert_metric("2024-01-15", "steps", 8500.0, "apple_health")
    db.insert_metric("2024-01-16", "mood", 7.0, "manual")
    metrics = db.get_metrics()
    assert len(metrics) == 2


def test_query_metrics_by_name(db):
    """Query metrics filtered by name."""
    db.insert_metric("2024-01-15", "steps", 8500.0, "apple_health")
    db.insert_metric("2024-01-15", "mood", 7.0, "manual")
    metrics = db.get_metrics(name="steps")
    assert len(metrics) == 1
    assert metrics[0].metric_name == "steps"


def test_query_metrics_by_date_range(db):
    """Query metrics filtered by date range."""
    db.insert_metric("2024-01-14", "steps", 7000.0, "apple_health")
    db.insert_metric("2024-01-15", "steps", 8500.0, "apple_health")
    db.insert_metric("2024-01-16", "steps", 9000.0, "apple_health")
    metrics = db.get_metrics(from_date="2024-01-15", to_date="2024-01-15")
    assert len(metrics) == 1
    assert metrics[0].date == "2024-01-15"


def test_get_metrics_df(db):
    """Get metrics as DataFrame."""
    db.insert_metric("2024-01-15", "steps", 8500.0, "apple_health")
    db.insert_metric("2024-01-15", "mood", 7.0, "manual")
    db.insert_metric("2024-01-16", "steps", 9000.0, "apple_health")
    
    df = db.get_metrics_df()
    assert "steps" in df.columns
    assert "mood" in df.columns
    assert len(df) == 2


def test_get_metrics_df_empty(db):
    """Get metrics DataFrame when empty."""
    df = db.get_metrics_df()
    assert df.empty


def test_get_metrics_df_date_index(db):
    """DataFrame has datetime index."""
    db.insert_metric("2024-01-15", "steps", 8500.0, "apple_health")
    df = db.get_metrics_df()
    assert str(df.index[0].date()) == "2024-01-15"


def test_list_metric_names(db):
    """List all unique metric names."""
    db.insert_metric("2024-01-15", "steps", 8500.0, "apple_health")
    db.insert_metric("2024-01-15", "mood", 7.0, "manual")
    db.insert_metric("2024-01-16", "steps", 9000.0, "apple_health")
    
    names = db.get_metric_names()
    assert names == ["mood", "steps"]  # Sorted


def test_get_date_range_all(db):
    """Get date range for all metrics."""
    db.insert_metric("2024-01-10", "steps", 8000.0, "apple_health")
    db.insert_metric("2024-01-20", "steps", 9000.0, "apple_health")
    
    date_range = db.get_date_range()
    assert date_range == ("2024-01-10", "2024-01-20")


def test_get_date_range_for_metric(db):
    """Get date range for specific metric."""
    db.insert_metric("2024-01-10", "steps", 8000.0, "apple_health")
    db.insert_metric("2024-01-15", "mood", 7.0, "manual")
    db.insert_metric("2024-01-20", "steps", 9000.0, "apple_health")
    
    date_range = db.get_date_range(metric="mood")
    assert date_range == ("2024-01-15", "2024-01-15")


def test_get_date_range_empty(db):
    """Get date range returns None when empty."""
    date_range = db.get_date_range()
    assert date_range is None


def test_insert_pattern(db):
    """Insert a discovered pattern."""
    pattern = PatternRecord(
        metric1="sleep_hours",
        metric2="mood",
        correlation=0.72,
        p_value=0.001,
        lag_days=1,
        sample_size=50,
        confidence="high",
    )
    db.insert_pattern(pattern)
    patterns = db.get_patterns()
    assert len(patterns) == 1
    assert patterns[0].correlation == 0.72


def test_query_patterns(db):
    """Query all patterns."""
    for i, conf in enumerate(["low", "medium", "high"]):
        pattern = PatternRecord(
            metric1=f"m{i}",
            metric2="mood",
            correlation=0.3 + i * 0.2,
            p_value=0.01,
            lag_days=0,
            sample_size=30,
            confidence=conf,
        )
        db.insert_pattern(pattern)
    
    patterns = db.get_patterns()
    assert len(patterns) == 3


def test_query_patterns_by_confidence(db):
    """Query patterns filtered by minimum confidence."""
    for i, conf in enumerate(["low", "medium", "high"]):
        pattern = PatternRecord(
            metric1=f"m{i}",
            metric2="mood",
            correlation=0.3 + i * 0.2,
            p_value=0.01,
            lag_days=0,
            sample_size=30,
            confidence=conf,
        )
        db.insert_pattern(pattern)
    
    patterns = db.get_patterns(min_confidence="medium")
    assert len(patterns) == 2
    confidences = {p.confidence for p in patterns}
    assert "low" not in confidences


def test_insert_event(db):
    """Insert a manual event."""
    event = EventRecord(
        timestamp="2024-01-15T14:30:00",
        event_type="mood",
        value=7.0,
        note="Good day",
        tags=["work", "productive"],
    )
    db.insert_event(event)
    events = db.get_events()
    assert len(events) == 1
    assert events[0].value == 7.0
    assert events[0].tags == ["work", "productive"]


def test_query_events(db):
    """Query all events."""
    for day in [15, 16, 17]:
        event = EventRecord(
            timestamp=f"2024-01-{day}T10:00:00",
            event_type="mood",
            value=float(day - 10),
        )
        db.insert_event(event)
    
    events = db.get_events()
    assert len(events) == 3


def test_query_events_by_date(db):
    """Query events filtered by date range."""
    for day in [15, 16, 17]:
        event = EventRecord(
            timestamp=f"2024-01-{day}T10:00:00",
            event_type="mood",
            value=float(day - 10),
        )
        db.insert_event(event)
    
    events = db.get_events(from_date="2024-01-16", to_date="2024-01-16")
    assert len(events) == 1
    assert "2024-01-16" in events[0].timestamp


def test_get_metric_count(db):
    """Get count of metric records."""
    db.insert_metric("2024-01-15", "steps", 8500.0, "apple_health")
    db.insert_metric("2024-01-15", "mood", 7.0, "manual")
    db.insert_metric("2024-01-16", "steps", 9000.0, "apple_health")
    
    assert db.get_metric_count() == 3
    assert db.get_metric_count(metric="steps") == 2


def test_get_last_analysis_date_no_patterns(db):
    """Returns None when no patterns exist."""
    result = db.get_last_analysis_date()
    assert result is None


def test_get_last_analysis_date_with_patterns(db):
    """Returns the most recent discovered_at timestamp."""
    pattern = PatternRecord(
        metric1="steps",
        metric2="mood",
        correlation=0.5,
        p_value=0.01,
        lag_days=0,
        sample_size=30,
        confidence="high",
    )
    db.insert_pattern(pattern)
    
    result = db.get_last_analysis_date()
    assert result is not None
    # Should be a date-like string (format: YYYY-MM-DD HH:MM)
    assert len(result) == 16
    assert "-" in result
