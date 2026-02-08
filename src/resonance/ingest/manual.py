"""Manual metric logging."""

from __future__ import annotations

from datetime import date, datetime

from ..database import Database
from ..models import EventRecord


def log_metric(
    db: Database,
    metric: str,
    value: float,
    note: str | None = None,
    tags: list[str] | None = None,
) -> None:
    """Log a manual metric value for today.
    
    Args:
        db: Database instance.
        metric: Metric name (e.g., 'mood', 'energy').
        value: Numeric value.
        note: Optional note about the entry.
        tags: Optional list of tags.
    """
    today = date.today().isoformat()
    
    # Normalize metric name
    metric = normalize_metric_name(metric)
    
    # Insert the metric
    db.insert_metric(today, metric, value, "manual")
    
    # If there's a note or tags, also create an event
    if note or tags:
        event = EventRecord(
            timestamp=datetime.now().isoformat(),
            event_type=metric,
            value=value,
            note=note,
            tags=tags or [],
        )
        db.insert_event(event)


def log_event(
    db: Database,
    event_type: str,
    value: float | None = None,
    note: str | None = None,
    tags: list[str] | None = None,
) -> None:
    """Log an event with optional value.
    
    Use this for events that don't have a daily metric (e.g., notes).
    
    Args:
        db: Database instance.
        event_type: Type of event.
        value: Optional numeric value.
        note: Optional note.
        tags: Optional list of tags.
    """
    event = EventRecord(
        timestamp=datetime.now().isoformat(),
        event_type=normalize_metric_name(event_type),
        value=value,
        note=note,
        tags=tags or [],
    )
    db.insert_event(event)


def parse_tags(tag_string: str | None) -> list[str]:
    """Parse comma-separated tag string.
    
    Args:
        tag_string: Comma-separated tags like "work, productive, morning".
        
    Returns:
        List of cleaned tag strings.
    """
    if not tag_string:
        return []
    return [t.strip().lower() for t in tag_string.split(",") if t.strip()]


def normalize_metric_name(name: str) -> str:
    """Normalize metric name to lowercase with underscores.
    
    Args:
        name: Raw metric name.
        
    Returns:
        Normalized name (lowercase, spaces to underscores).
    """
    return name.lower().strip().replace(" ", "_").replace("-", "_")


def validate_metric_value(metric: str, value: float) -> tuple[bool, str]:
    """Validate metric value is in expected range.
    
    Args:
        metric: Metric name.
        value: Value to validate.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    # Standard 1-10 scale metrics
    scale_metrics = {"mood", "energy", "stress", "focus", "motivation"}
    
    if metric in scale_metrics:
        if not 1 <= value <= 10:
            return False, f"{metric} should be between 1 and 10"
    
    # Positive-only metrics
    if value < 0:
        return False, f"{metric} cannot be negative"
    
    return True, ""
