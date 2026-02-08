"""Tests for Apple Health import."""

import pytest
from pathlib import Path
from datetime import datetime

from resonance.ingest.health import (
    parse_date,
    parse_health_export,
    aggregate_daily,
    import_health,
    get_supported_metrics,
    SUPPORTED_TYPES,
)
from resonance.models import HealthRecord
from resonance.database import Database


@pytest.fixture
def sample_health_xml(temp_dir):
    """Create a sample Apple Health export XML."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
    <Record type="HKQuantityTypeIdentifierStepCount" 
            value="1500" unit="count"
            startDate="2024-01-15 10:00:00 -0500"
            endDate="2024-01-15 10:30:00 -0500"/>
    <Record type="HKQuantityTypeIdentifierStepCount" 
            value="2000" unit="count"
            startDate="2024-01-15 14:00:00 -0500"
            endDate="2024-01-15 14:30:00 -0500"/>
    <Record type="HKQuantityTypeIdentifierStepCount" 
            value="3000" unit="count"
            startDate="2024-01-16 09:00:00 -0500"
            endDate="2024-01-16 09:30:00 -0500"/>
    <Record type="HKCategoryTypeIdentifierSleepAnalysis"
            value="HKCategoryValueSleepAnalysisAsleepCore"
            startDate="2024-01-15 23:00:00 -0500"
            endDate="2024-01-16 02:00:00 -0500"/>
    <Record type="HKCategoryTypeIdentifierSleepAnalysis"
            value="HKCategoryValueSleepAnalysisAsleepDeep"
            startDate="2024-01-16 02:00:00 -0500"
            endDate="2024-01-16 05:00:00 -0500"/>
    <Record type="HKQuantityTypeIdentifierHeartRate"
            value="72" unit="count/min"
            startDate="2024-01-15 10:00:00 -0500"
            endDate="2024-01-15 10:00:00 -0500"/>
    <Record type="HKQuantityTypeIdentifierHeartRate"
            value="68" unit="count/min"
            startDate="2024-01-15 14:00:00 -0500"
            endDate="2024-01-15 14:00:00 -0500"/>
    <Record type="HKQuantityTypeIdentifierBodyMass"
            value="75.5" unit="kg"
            startDate="2024-01-15 08:00:00 -0500"
            endDate="2024-01-15 08:00:00 -0500"/>
    <Record type="HKQuantityTypeIdentifierBodyMass"
            value="75.3" unit="kg"
            startDate="2024-01-15 20:00:00 -0500"
            endDate="2024-01-15 20:00:00 -0500"/>
    <Record type="HKQuantityTypeIdentifierDistanceWalkingRunning"
            value="1.2" unit="km"
            startDate="2024-01-15 10:00:00 -0500"
            endDate="2024-01-15 10:30:00 -0500"/>
</HealthData>
"""
    path = temp_dir / "export.xml"
    path.write_text(xml_content)
    return path


@pytest.fixture
def empty_health_xml(temp_dir):
    """Create an empty Apple Health export XML."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
</HealthData>
"""
    path = temp_dir / "empty.xml"
    path.write_text(xml_content)
    return path


def test_parse_date_with_timezone():
    """Parse date with timezone offset."""
    dt = parse_date("2024-01-15 10:30:00 -0500")
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 15
    assert dt.hour == 10
    assert dt.minute == 30


def test_parse_date_without_timezone():
    """Parse date without timezone."""
    dt = parse_date("2024-01-15 10:30:00")
    assert dt.day == 15


def test_parse_date_iso_format():
    """Parse ISO format date."""
    dt = parse_date("2024-01-15T10:30:00")
    assert dt.day == 15


def test_parse_step_count_record(sample_health_xml):
    """Parse step count records."""
    records = list(parse_health_export(sample_health_xml))
    step_records = [r for r in records if r.record_type == "HKQuantityTypeIdentifierStepCount"]
    assert len(step_records) == 3
    assert step_records[0].value == 1500.0


def test_parse_sleep_record(sample_health_xml):
    """Parse sleep records (calculates duration)."""
    records = list(parse_health_export(sample_health_xml))
    sleep_records = [r for r in records if r.record_type == "HKCategoryTypeIdentifierSleepAnalysis"]
    assert len(sleep_records) == 2
    # First sleep record: 23:00 to 02:00 = 3 hours
    assert sleep_records[0].value == 3.0


def test_parse_heart_rate_record(sample_health_xml):
    """Parse heart rate records."""
    records = list(parse_health_export(sample_health_xml))
    hr_records = [r for r in records if r.record_type == "HKQuantityTypeIdentifierHeartRate"]
    assert len(hr_records) == 2
    assert hr_records[0].value == 72.0


def test_parse_distance_record(sample_health_xml):
    """Parse distance records."""
    records = list(parse_health_export(sample_health_xml))
    dist_records = [r for r in records if r.record_type == "HKQuantityTypeIdentifierDistanceWalkingRunning"]
    assert len(dist_records) == 1
    assert dist_records[0].value == 1.2


def test_parse_weight_record(sample_health_xml):
    """Parse weight records."""
    records = list(parse_health_export(sample_health_xml))
    weight_records = [r for r in records if r.record_type == "HKQuantityTypeIdentifierBodyMass"]
    assert len(weight_records) == 2


def test_aggregate_steps_sums_daily(sample_health_xml):
    """Steps are summed per day."""
    records = parse_health_export(sample_health_xml)
    daily = aggregate_daily(records)
    
    steps_jan15 = [m for m in daily if m.date == "2024-01-15" and m.metric_name == "steps"]
    assert len(steps_jan15) == 1
    assert steps_jan15[0].value == 3500.0  # 1500 + 2000


def test_aggregate_sleep_sums_nightly(sample_health_xml):
    """Sleep hours are summed per night."""
    records = parse_health_export(sample_health_xml)
    daily = aggregate_daily(records)
    
    # Both sleep records start on 2024-01-15 (even though one ends on 16th)
    sleep_jan15 = [m for m in daily if m.date == "2024-01-15" and m.metric_name == "sleep_hours"]
    assert len(sleep_jan15) == 1
    assert sleep_jan15[0].value == 3.0  # First record only (starts on 15th)


def test_aggregate_heart_rate_averages(sample_health_xml):
    """Heart rate is averaged per day."""
    records = parse_health_export(sample_health_xml)
    daily = aggregate_daily(records)
    
    hr_jan15 = [m for m in daily if m.date == "2024-01-15" and m.metric_name == "heart_rate_avg"]
    assert len(hr_jan15) == 1
    assert hr_jan15[0].value == 70.0  # (72 + 68) / 2


def test_aggregate_weight_takes_last(sample_health_xml):
    """Weight takes last reading of the day."""
    records = parse_health_export(sample_health_xml)
    daily = aggregate_daily(records)
    
    weight_jan15 = [m for m in daily if m.date == "2024-01-15" and m.metric_name == "weight_kg"]
    assert len(weight_jan15) == 1
    assert weight_jan15[0].value == 75.3  # Last reading (20:00)


def test_handle_empty_export(empty_health_xml):
    """Handle empty export file."""
    records = list(parse_health_export(empty_health_xml))
    assert records == []


def test_skip_unsupported_types(temp_dir):
    """Skip unsupported record types."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
    <Record type="HKQuantityTypeIdentifierUnknownType"
            value="100"
            startDate="2024-01-15 10:00:00 -0500"
            endDate="2024-01-15 10:30:00 -0500"/>
</HealthData>
"""
    path = temp_dir / "unknown.xml"
    path.write_text(xml_content)
    records = list(parse_health_export(path))
    assert records == []


def test_import_to_database(sample_health_xml, temp_db):
    """Import health data to database."""
    db = Database(temp_db)
    count = import_health(db, sample_health_xml)
    assert count > 0
    
    metrics = db.get_metrics()
    assert len(metrics) > 0
    db.close()


def test_import_file_not_found(temp_db):
    """Import raises error for missing file."""
    db = Database(temp_db)
    with pytest.raises(FileNotFoundError):
        import_health(db, Path("/nonexistent/export.xml"))
    db.close()


def test_get_supported_metrics():
    """Get list of supported metric names."""
    metrics = get_supported_metrics()
    assert "steps" in metrics
    assert "sleep_hours" in metrics
    assert "heart_rate_avg" in metrics
