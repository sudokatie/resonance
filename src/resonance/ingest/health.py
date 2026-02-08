"""Apple Health export XML parser."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterator
import xml.etree.ElementTree as ET

from ..database import Database
from ..models import HealthRecord, MetricRecord


# Map Apple Health record types to metric names and aggregation methods
# Format: HK type -> (metric_name, aggregation_method)
# Aggregation: 'sum' = add values, 'avg' = average, 'last' = latest value
SUPPORTED_TYPES: dict[str, tuple[str, str]] = {
    "HKQuantityTypeIdentifierStepCount": ("steps", "sum"),
    "HKQuantityTypeIdentifierDistanceWalkingRunning": ("distance_km", "sum"),
    "HKQuantityTypeIdentifierActiveEnergyBurned": ("active_calories", "sum"),
    "HKCategoryTypeIdentifierSleepAnalysis": ("sleep_hours", "sum"),
    "HKQuantityTypeIdentifierHeartRate": ("heart_rate_avg", "avg"),
    "HKQuantityTypeIdentifierRestingHeartRate": ("resting_hr", "avg"),
    "HKQuantityTypeIdentifierBodyMass": ("weight_kg", "last"),
}

# Sleep types that count as actual sleep (not just "in bed")
SLEEP_TYPES = {"HKCategoryValueSleepAnalysisAsleepCore", 
               "HKCategoryValueSleepAnalysisAsleepDeep",
               "HKCategoryValueSleepAnalysisAsleepREM",
               "HKCategoryValueSleepAnalysisAsleep"}


def parse_date(date_str: str) -> datetime:
    """Parse Apple Health date string to datetime.
    
    Apple Health uses format like: 2024-01-15 10:30:00 -0500
    """
    # Remove timezone for simplicity (we care about local time)
    if " -" in date_str or " +" in date_str:
        date_str = date_str.rsplit(" ", 1)[0]
    
    # Try common formats
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Cannot parse date: {date_str}")


def parse_health_export(path: Path) -> Iterator[HealthRecord]:
    """Stream parse Apple Health export XML.
    
    Uses iterparse for memory efficiency with large exports.
    
    Args:
        path: Path to export.xml file.
        
    Yields:
        HealthRecord for each supported record type.
    """
    for event, elem in ET.iterparse(str(path), events=["end"]):
        if elem.tag == "Record":
            record_type = elem.get("type", "")
            
            if record_type in SUPPORTED_TYPES:
                # Handle sleep specially (uses value attribute for sleep type)
                if record_type == "HKCategoryTypeIdentifierSleepAnalysis":
                    sleep_value = elem.get("value", "")
                    if sleep_value not in SLEEP_TYPES:
                        elem.clear()
                        continue
                
                try:
                    start_date = parse_date(elem.get("startDate", ""))
                    end_date = parse_date(elem.get("endDate", ""))
                    
                    # For sleep, value is duration in hours
                    if record_type == "HKCategoryTypeIdentifierSleepAnalysis":
                        value = (end_date - start_date).total_seconds() / 3600
                    else:
                        value = float(elem.get("value", 0))
                    
                    yield HealthRecord(
                        record_type=record_type,
                        value=value,
                        unit=elem.get("unit", ""),
                        start_date=start_date,
                        end_date=end_date,
                    )
                except (ValueError, TypeError):
                    # Skip malformed records
                    pass
            
            # Free memory
            elem.clear()


def aggregate_daily(records: Iterator[HealthRecord]) -> list[MetricRecord]:
    """Aggregate health records to daily metrics.
    
    Args:
        records: Iterator of HealthRecord objects.
        
    Returns:
        List of MetricRecord with one entry per date/metric.
    """
    # Group by date and metric name
    daily: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    
    for record in records:
        metric_info = SUPPORTED_TYPES.get(record.record_type)
        if metric_info:
            metric_name, _ = metric_info
            date = record.start_date.date().isoformat()
            daily[date][metric_name].append(record.value)
    
    # Aggregate values
    results: list[MetricRecord] = []
    for date in sorted(daily.keys()):
        for metric_name, values in daily[date].items():
            # Find aggregation method
            agg_method = "sum"
            for hk_type, (name, method) in SUPPORTED_TYPES.items():
                if name == metric_name:
                    agg_method = method
                    break
            
            if agg_method == "sum":
                final_value = sum(values)
            elif agg_method == "avg":
                final_value = sum(values) / len(values)
            elif agg_method == "last":
                final_value = values[-1]
            else:
                final_value = sum(values)
            
            results.append(MetricRecord(
                date=date,
                metric_name=metric_name,
                value=final_value,
                source="apple_health",
            ))
    
    return results


def import_health(
    db: Database,
    path: Path,
    dry_run: bool = False,
) -> int:
    """Import Apple Health export to database.
    
    Args:
        db: Database instance.
        path: Path to export.xml file.
        dry_run: If True, don't actually insert.
        
    Returns:
        Number of daily metrics imported.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    # Parse and aggregate
    records = parse_health_export(path)
    daily_metrics = aggregate_daily(records)
    
    if dry_run:
        return len(daily_metrics)
    
    # Insert to database
    return db.insert_metrics(daily_metrics)


def get_supported_metrics() -> list[str]:
    """Get list of metric names we can import from Health.
    
    Returns:
        List of metric names.
    """
    return sorted(set(name for name, _ in SUPPORTED_TYPES.values()))
