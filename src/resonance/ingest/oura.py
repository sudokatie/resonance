"""Oura Ring API integration.

Uses personal access token for authentication.
Oura provides high-quality sleep and readiness data.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..database import Database
from ..models import MetricRecord

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore


# Oura API endpoints
API_BASE = "https://api.ouraring.com/v2/usercollection"

# Map Oura data to metric names
# Sleep data provides the richest metrics
SLEEP_METRICS = [
    ("total_sleep_duration", "sleep_hours", lambda x: x / 3600),  # seconds to hours
    ("efficiency", "sleep_efficiency", lambda x: x),  # percentage
    ("deep_sleep_duration", "deep_sleep_hours", lambda x: x / 3600),
    ("rem_sleep_duration", "rem_sleep_hours", lambda x: x / 3600),
    ("light_sleep_duration", "light_sleep_hours", lambda x: x / 3600),
    ("restless_periods", "sleep_restless", lambda x: x),
    ("average_heart_rate", "sleep_hr_avg", lambda x: x),
    ("lowest_heart_rate", "sleep_hr_min", lambda x: x),
    ("average_hrv", "hrv_avg", lambda x: x),
]

READINESS_METRICS = [
    ("score", "readiness_score", lambda x: x),
    ("temperature_deviation", "temp_deviation", lambda x: x),
]

ACTIVITY_METRICS = [
    ("steps", "steps", lambda x: x),
    ("active_calories", "active_calories", lambda x: x),
    ("total_calories", "total_calories", lambda x: x),
    ("equivalent_walking_distance", "distance_km", lambda x: x / 1000),  # meters to km
]


def get_token_path() -> Path:
    """Get path to token file."""
    config_dir = Path.home() / ".config" / "resonance"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "oura_token.json"


def save_token(token: str) -> None:
    """Save API token to file."""
    path = get_token_path()
    with open(path, "w") as f:
        json.dump({"token": token}, f)


def load_token() -> str | None:
    """Load API token from file."""
    path = get_token_path()
    if not path.exists():
        return None
    
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("token")
    except (json.JSONDecodeError, KeyError):
        return None


def get_valid_token(token: str | None = None) -> str:
    """Get a valid API token.
    
    Args:
        token: API token to use (or load from file).
        
    Returns:
        Valid API token.
        
    Raises:
        ValueError: If no token provided or saved.
    """
    if token:
        save_token(token)
        return token
    
    saved_token = load_token()
    if saved_token:
        return saved_token
    
    raise ValueError(
        "No Oura API token. Get your personal access token from "
        "https://cloud.ouraring.com/personal-access-tokens and provide it "
        "with --token"
    )


def fetch_sleep_data(
    token: str,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Fetch sleep data from Oura API.
    
    Args:
        token: API token.
        start_date: Start of date range.
        end_date: End of date range.
        
    Returns:
        List of sleep records.
    """
    if httpx is None:
        raise ImportError("httpx is required for Oura integration")
    
    url = f"{API_BASE}/sleep"
    params = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }
    headers = {"Authorization": f"Bearer {token}"}
    
    response = httpx.get(url, params=params, headers=headers, timeout=30.0)
    response.raise_for_status()
    
    return response.json().get("data", [])


def fetch_daily_readiness(
    token: str,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Fetch daily readiness data from Oura API.
    
    Args:
        token: API token.
        start_date: Start of date range.
        end_date: End of date range.
        
    Returns:
        List of readiness records.
    """
    if httpx is None:
        raise ImportError("httpx is required for Oura integration")
    
    url = f"{API_BASE}/daily_readiness"
    params = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }
    headers = {"Authorization": f"Bearer {token}"}
    
    response = httpx.get(url, params=params, headers=headers, timeout=30.0)
    response.raise_for_status()
    
    return response.json().get("data", [])


def fetch_daily_activity(
    token: str,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Fetch daily activity data from Oura API.
    
    Args:
        token: API token.
        start_date: Start of date range.
        end_date: End of date range.
        
    Returns:
        List of activity records.
    """
    if httpx is None:
        raise ImportError("httpx is required for Oura integration")
    
    url = f"{API_BASE}/daily_activity"
    params = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }
    headers = {"Authorization": f"Bearer {token}"}
    
    response = httpx.get(url, params=params, headers=headers, timeout=30.0)
    response.raise_for_status()
    
    return response.json().get("data", [])


def parse_sleep_metrics(records: list[dict[str, Any]]) -> list[MetricRecord]:
    """Parse sleep records to metrics.
    
    Args:
        records: Sleep records from API.
        
    Returns:
        List of MetricRecord.
    """
    metrics: list[MetricRecord] = []
    
    for record in records:
        # Get date from day field
        date_str = record.get("day")
        if not date_str:
            continue
        
        for api_field, metric_name, transform in SLEEP_METRICS:
            value = record.get(api_field)
            if value is not None:
                try:
                    transformed = transform(float(value))
                    metrics.append(MetricRecord(
                        date=date_str,
                        metric_name=metric_name,
                        value=transformed,
                        source="oura",
                    ))
                except (ValueError, TypeError):
                    continue
    
    return metrics


def parse_readiness_metrics(records: list[dict[str, Any]]) -> list[MetricRecord]:
    """Parse readiness records to metrics.
    
    Args:
        records: Readiness records from API.
        
    Returns:
        List of MetricRecord.
    """
    metrics: list[MetricRecord] = []
    
    for record in records:
        date_str = record.get("day")
        if not date_str:
            continue
        
        for api_field, metric_name, transform in READINESS_METRICS:
            value = record.get(api_field)
            if value is not None:
                try:
                    transformed = transform(float(value))
                    metrics.append(MetricRecord(
                        date=date_str,
                        metric_name=metric_name,
                        value=transformed,
                        source="oura",
                    ))
                except (ValueError, TypeError):
                    continue
    
    return metrics


def parse_activity_metrics(records: list[dict[str, Any]]) -> list[MetricRecord]:
    """Parse activity records to metrics.
    
    Args:
        records: Activity records from API.
        
    Returns:
        List of MetricRecord.
    """
    metrics: list[MetricRecord] = []
    
    for record in records:
        date_str = record.get("day")
        if not date_str:
            continue
        
        for api_field, metric_name, transform in ACTIVITY_METRICS:
            value = record.get(api_field)
            if value is not None:
                try:
                    transformed = transform(float(value))
                    metrics.append(MetricRecord(
                        date=date_str,
                        metric_name=metric_name,
                        value=transformed,
                        source="oura",
                    ))
                except (ValueError, TypeError):
                    continue
    
    return metrics


def import_oura(
    db: Database,
    days: int = 30,
    token: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    console: Any = None,
) -> int:
    """Import data from Oura Ring.
    
    Args:
        db: Database instance.
        days: Number of days to import.
        token: Oura personal access token.
        dry_run: If True, don't actually insert.
        verbose: If True, log each metric.
        console: Rich console for output.
        
    Returns:
        Number of metrics imported.
    """
    if httpx is None:
        raise ImportError(
            "httpx is required for Oura integration. "
            "Install with: pip install httpx"
        )
    
    # Get token
    api_token = get_valid_token(token)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    all_metrics: list[MetricRecord] = []
    
    # Fetch sleep data
    if verbose and console:
        console.print("  Fetching sleep data...")
    try:
        sleep_records = fetch_sleep_data(api_token, start_date, end_date)
        sleep_metrics = parse_sleep_metrics(sleep_records)
        all_metrics.extend(sleep_metrics)
        if verbose and console:
            console.print(f"    Found {len(sleep_metrics)} sleep metrics")
    except Exception as e:
        if verbose and console:
            console.print(f"    Error fetching sleep: {e}", style="yellow")
    
    # Fetch readiness data
    if verbose and console:
        console.print("  Fetching readiness data...")
    try:
        readiness_records = fetch_daily_readiness(api_token, start_date, end_date)
        readiness_metrics = parse_readiness_metrics(readiness_records)
        all_metrics.extend(readiness_metrics)
        if verbose and console:
            console.print(f"    Found {len(readiness_metrics)} readiness metrics")
    except Exception as e:
        if verbose and console:
            console.print(f"    Error fetching readiness: {e}", style="yellow")
    
    # Fetch activity data
    if verbose and console:
        console.print("  Fetching activity data...")
    try:
        activity_records = fetch_daily_activity(api_token, start_date, end_date)
        activity_metrics = parse_activity_metrics(activity_records)
        all_metrics.extend(activity_metrics)
        if verbose and console:
            console.print(f"    Found {len(activity_metrics)} activity metrics")
    except Exception as e:
        if verbose and console:
            console.print(f"    Error fetching activity: {e}", style="yellow")
    
    if verbose and console:
        for metric in all_metrics:
            console.print(f"    {metric.date}: {metric.metric_name} = {metric.value:.2f}")
    
    if dry_run:
        return len(all_metrics)
    
    return db.insert_metrics(all_metrics)


def get_supported_metrics() -> list[str]:
    """Get list of metric names we can import from Oura."""
    metrics: set[str] = set()
    for _, name, _ in SLEEP_METRICS:
        metrics.add(name)
    for _, name, _ in READINESS_METRICS:
        metrics.add(name)
    for _, name, _ in ACTIVITY_METRICS:
        metrics.add(name)
    return sorted(metrics)
