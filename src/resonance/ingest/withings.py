"""Withings API integration.

Uses OAuth2 for authentication.
Withings provides weight, blood pressure, and sleep data from their smart devices.
"""

from __future__ import annotations

import json
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, parse_qs, urlparse

from ..database import Database
from ..models import MetricRecord

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore


# Withings API endpoints
AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
MEASURE_URL = "https://wbsapi.withings.net/measure"
SLEEP_URL = "https://wbsapi.withings.net/v2/sleep"

# OAuth scopes
SCOPES = ["user.metrics", "user.activity"]

# Measure types (from Withings API docs)
# https://developer.withings.com/api-reference#tag/measure/operation/measure-getmeas
MEASURE_TYPES = {
    1: ("weight_kg", lambda x: x),
    4: ("height_m", lambda x: x),
    5: ("fat_free_mass_kg", lambda x: x),
    6: ("fat_ratio", lambda x: x),
    8: ("fat_mass_kg", lambda x: x),
    9: ("diastolic_bp", lambda x: x),
    10: ("systolic_bp", lambda x: x),
    11: ("heart_rate", lambda x: x),
    12: ("temperature_c", lambda x: x),
    54: ("sp02", lambda x: x),
    71: ("body_temp_c", lambda x: x),
    73: ("skin_temp_c", lambda x: x),
    76: ("muscle_mass_kg", lambda x: x),
    77: ("hydration_kg", lambda x: x),
    88: ("bone_mass_kg", lambda x: x),
    91: ("pulse_wave_velocity", lambda x: x),
}

# Sleep state mapping
SLEEP_STATES = {
    0: "awake",
    1: "light_sleep",
    2: "deep_sleep",
    3: "rem_sleep",
}


@dataclass
class WithingsCredentials:
    """OAuth credentials for Withings."""
    
    access_token: str
    refresh_token: str
    expires_at: float
    client_id: str
    client_secret: str
    user_id: str
    
    def is_expired(self) -> bool:
        """Check if access token is expired."""
        return time.time() >= self.expires_at - 60  # 60s buffer
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "user_id": self.user_id,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WithingsCredentials:
        """Create from dictionary."""
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            user_id=data.get("user_id", ""),
        )


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback with authorization code."""
    
    auth_code: str | None = None
    
    def do_GET(self) -> None:
        """Handle GET request with auth code."""
        query = parse_qs(urlparse(self.path).query)
        
        if "code" in query:
            OAuthCallbackHandler.auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body>
                <h1>Authorization successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                </body></html>
            """)
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            error = query.get("error", ["Unknown error"])[0]
            self.wfile.write(f"""
                <html><body>
                <h1>Authorization failed</h1>
                <p>Error: {error}</p>
                </body></html>
            """.encode())
    
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress log messages."""
        pass


def get_credentials_path() -> Path:
    """Get path to credentials file."""
    config_dir = Path.home() / ".config" / "resonance"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "withings_credentials.json"


def save_credentials(creds: WithingsCredentials) -> None:
    """Save credentials to file."""
    path = get_credentials_path()
    with open(path, "w") as f:
        json.dump(creds.to_dict(), f)


def load_credentials() -> WithingsCredentials | None:
    """Load credentials from file."""
    path = get_credentials_path()
    if not path.exists():
        return None
    
    try:
        with open(path) as f:
            data = json.load(f)
        return WithingsCredentials.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def refresh_access_token(creds: WithingsCredentials) -> WithingsCredentials:
    """Refresh expired access token.
    
    Args:
        creds: Current credentials with refresh token.
        
    Returns:
        Updated credentials with new access token.
    """
    if httpx is None:
        raise ImportError("httpx is required for Withings integration")
    
    data = {
        "action": "requesttoken",
        "grant_type": "refresh_token",
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
    }
    
    response = httpx.post(TOKEN_URL, data=data, timeout=30.0)
    response.raise_for_status()
    
    result = response.json()
    if result.get("status") != 0:
        raise ValueError(f"Token refresh failed: {result.get('error', 'Unknown error')}")
    
    body = result.get("body", {})
    new_creds = WithingsCredentials(
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        expires_at=time.time() + body["expires_in"],
        client_id=creds.client_id,
        client_secret=creds.client_secret,
        user_id=body.get("userid", creds.user_id),
    )
    
    save_credentials(new_creds)
    return new_creds


def authorize(
    client_id: str,
    client_secret: str,
    redirect_port: int = 8765,
) -> WithingsCredentials:
    """Run OAuth flow to authorize with Withings.
    
    Args:
        client_id: Withings OAuth client ID.
        client_secret: Withings OAuth client secret.
        redirect_port: Port for OAuth callback server.
        
    Returns:
        OAuth credentials.
    """
    if httpx is None:
        raise ImportError("httpx is required for Withings integration")
    
    redirect_uri = f"http://localhost:{redirect_port}/callback"
    
    # Build authorization URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": ",".join(SCOPES),
        "state": "resonance",
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"
    
    # Start callback server
    OAuthCallbackHandler.auth_code = None
    server = HTTPServer(("localhost", redirect_port), OAuthCallbackHandler)
    server.timeout = 120
    
    # Open browser for authorization
    webbrowser.open(auth_url)
    
    # Wait for callback
    while OAuthCallbackHandler.auth_code is None:
        server.handle_request()
    
    auth_code = OAuthCallbackHandler.auth_code
    server.server_close()
    
    # Exchange code for tokens
    data = {
        "action": "requesttoken",
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "redirect_uri": redirect_uri,
    }
    
    response = httpx.post(TOKEN_URL, data=data, timeout=30.0)
    response.raise_for_status()
    
    result = response.json()
    if result.get("status") != 0:
        raise ValueError(f"Token exchange failed: {result.get('error', 'Unknown error')}")
    
    body = result.get("body", {})
    creds = WithingsCredentials(
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        expires_at=time.time() + body["expires_in"],
        client_id=client_id,
        client_secret=client_secret,
        user_id=body.get("userid", ""),
    )
    
    save_credentials(creds)
    return creds


def get_valid_credentials(
    client_id: str | None = None,
    client_secret: str | None = None,
) -> WithingsCredentials:
    """Get valid credentials, authorizing if needed.
    
    Args:
        client_id: OAuth client ID (required for first auth).
        client_secret: OAuth client secret (required for first auth).
        
    Returns:
        Valid credentials.
    """
    creds = load_credentials()
    
    if creds is None:
        if not client_id or not client_secret:
            raise ValueError(
                "No saved Withings credentials. Provide --client-id and --client-secret "
                "to authorize. Get these from https://developer.withings.com/"
            )
        return authorize(client_id, client_secret)
    
    if creds.is_expired():
        return refresh_access_token(creds)
    
    return creds


def fetch_measures(
    creds: WithingsCredentials,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Fetch measure data from Withings API.
    
    Args:
        creds: Valid credentials.
        start_date: Start of date range.
        end_date: End of date range.
        
    Returns:
        List of measure groups.
    """
    if httpx is None:
        raise ImportError("httpx is required for Withings integration")
    
    headers = {"Authorization": f"Bearer {creds.access_token}"}
    data = {
        "action": "getmeas",
        "startdate": int(start_date.timestamp()),
        "enddate": int(end_date.timestamp()),
    }
    
    response = httpx.post(MEASURE_URL, data=data, headers=headers, timeout=30.0)
    response.raise_for_status()
    
    result = response.json()
    if result.get("status") != 0:
        raise ValueError(f"Measure fetch failed: {result.get('error', 'Unknown error')}")
    
    return result.get("body", {}).get("measuregrps", [])


def fetch_sleep(
    creds: WithingsCredentials,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Fetch sleep data from Withings API.
    
    Args:
        creds: Valid credentials.
        start_date: Start of date range.
        end_date: End of date range.
        
    Returns:
        List of sleep records.
    """
    if httpx is None:
        raise ImportError("httpx is required for Withings integration")
    
    headers = {"Authorization": f"Bearer {creds.access_token}"}
    data = {
        "action": "getsummary",
        "startdateymd": start_date.strftime("%Y-%m-%d"),
        "enddateymd": end_date.strftime("%Y-%m-%d"),
    }
    
    response = httpx.post(SLEEP_URL, data=data, headers=headers, timeout=30.0)
    response.raise_for_status()
    
    result = response.json()
    if result.get("status") != 0:
        raise ValueError(f"Sleep fetch failed: {result.get('error', 'Unknown error')}")
    
    return result.get("body", {}).get("series", [])


def parse_measure_metrics(measure_groups: list[dict[str, Any]]) -> list[MetricRecord]:
    """Parse measure groups to metrics.
    
    Args:
        measure_groups: Measure groups from API.
        
    Returns:
        List of MetricRecord.
    """
    metrics: list[MetricRecord] = []
    
    for group in measure_groups:
        # Get date from timestamp
        grp_date = group.get("date")
        if not grp_date:
            continue
        
        date_str = datetime.fromtimestamp(grp_date).strftime("%Y-%m-%d")
        
        for measure in group.get("measures", []):
            measure_type = measure.get("type")
            if measure_type not in MEASURE_TYPES:
                continue
            
            metric_name, transform = MEASURE_TYPES[measure_type]
            
            # Withings stores values with unit power
            # actual_value = value * 10^unit
            value = measure.get("value", 0)
            unit = measure.get("unit", 0)
            actual_value = value * (10 ** unit)
            
            try:
                transformed = transform(float(actual_value))
                metrics.append(MetricRecord(
                    date=date_str,
                    metric_name=metric_name,
                    value=transformed,
                    source="withings",
                ))
            except (ValueError, TypeError):
                continue
    
    return metrics


def parse_sleep_metrics(sleep_records: list[dict[str, Any]]) -> list[MetricRecord]:
    """Parse sleep records to metrics.
    
    Args:
        sleep_records: Sleep records from API.
        
    Returns:
        List of MetricRecord.
    """
    metrics: list[MetricRecord] = []
    
    for record in sleep_records:
        date_str = record.get("date")
        if not date_str:
            continue
        
        data = record.get("data", {})
        
        # Total sleep duration (seconds to hours)
        total_sleep = data.get("total_sleep_time")
        if total_sleep is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="sleep_hours",
                value=total_sleep / 3600,
                source="withings",
            ))
        
        # Deep sleep (seconds to hours)
        deep_sleep = data.get("deepsleepduration")
        if deep_sleep is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="deep_sleep_hours",
                value=deep_sleep / 3600,
                source="withings",
            ))
        
        # Light sleep (seconds to hours)
        light_sleep = data.get("lightsleepduration")
        if light_sleep is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="light_sleep_hours",
                value=light_sleep / 3600,
                source="withings",
            ))
        
        # REM sleep (seconds to hours)
        rem_sleep = data.get("remsleepduration")
        if rem_sleep is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="rem_sleep_hours",
                value=rem_sleep / 3600,
                source="withings",
            ))
        
        # Wake up count
        wakeup_count = data.get("wakeupcount")
        if wakeup_count is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="wakeup_count",
                value=float(wakeup_count),
                source="withings",
            ))
        
        # Average heart rate during sleep
        hr_average = data.get("hr_average")
        if hr_average is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="sleep_hr_avg",
                value=float(hr_average),
                source="withings",
            ))
        
        # Min heart rate during sleep
        hr_min = data.get("hr_min")
        if hr_min is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="sleep_hr_min",
                value=float(hr_min),
                source="withings",
            ))
        
        # Max heart rate during sleep
        hr_max = data.get("hr_max")
        if hr_max is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="sleep_hr_max",
                value=float(hr_max),
                source="withings",
            ))
        
        # Breathing disturbances
        breathing = data.get("breathing_disturbances_intensity")
        if breathing is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="breathing_disturbances",
                value=float(breathing),
                source="withings",
            ))
        
        # Snoring duration (seconds to minutes)
        snoring = data.get("snoring")
        if snoring is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="snoring_minutes",
                value=snoring / 60,
                source="withings",
            ))
        
        # Sleep score (0-100)
        sleep_score = data.get("sleep_score")
        if sleep_score is not None:
            metrics.append(MetricRecord(
                date=date_str,
                metric_name="sleep_score",
                value=float(sleep_score),
                source="withings",
            ))
    
    return metrics


def import_withings(
    db: Database,
    days: int = 30,
    client_id: str | None = None,
    client_secret: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    console: Any = None,
) -> int:
    """Import data from Withings.
    
    Args:
        db: Database instance.
        days: Number of days to import.
        client_id: OAuth client ID.
        client_secret: OAuth client secret.
        dry_run: If True, don't actually insert.
        verbose: If True, log each metric.
        console: Rich console for output.
        
    Returns:
        Number of metrics imported.
    """
    if httpx is None:
        raise ImportError(
            "httpx is required for Withings integration. "
            "Install with: pip install httpx"
        )
    
    # Get credentials
    creds = get_valid_credentials(client_id, client_secret)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    all_metrics: list[MetricRecord] = []
    
    # Fetch measures (weight, blood pressure, etc.)
    if verbose and console:
        console.print("  Fetching measure data...")
    try:
        measure_groups = fetch_measures(creds, start_date, end_date)
        measure_metrics = parse_measure_metrics(measure_groups)
        all_metrics.extend(measure_metrics)
        if verbose and console:
            console.print(f"    Found {len(measure_metrics)} measure metrics")
    except Exception as e:
        if verbose and console:
            console.print(f"    Error fetching measures: {e}", style="yellow")
    
    # Fetch sleep data
    if verbose and console:
        console.print("  Fetching sleep data...")
    try:
        sleep_records = fetch_sleep(creds, start_date, end_date)
        sleep_metrics = parse_sleep_metrics(sleep_records)
        all_metrics.extend(sleep_metrics)
        if verbose and console:
            console.print(f"    Found {len(sleep_metrics)} sleep metrics")
    except Exception as e:
        if verbose and console:
            console.print(f"    Error fetching sleep: {e}", style="yellow")
    
    if verbose and console:
        for metric in all_metrics:
            console.print(f"    {metric.date}: {metric.metric_name} = {metric.value:.2f}")
    
    if dry_run:
        return len(all_metrics)
    
    return db.insert_metrics(all_metrics)


def get_supported_metrics() -> list[str]:
    """Get list of metric names we can import from Withings."""
    metrics: set[str] = set()
    
    # Measure metrics
    for _, (name, _) in MEASURE_TYPES.items():
        metrics.add(name)
    
    # Sleep metrics
    metrics.update([
        "sleep_hours",
        "deep_sleep_hours",
        "light_sleep_hours",
        "rem_sleep_hours",
        "wakeup_count",
        "sleep_hr_avg",
        "sleep_hr_min",
        "sleep_hr_max",
        "breathing_disturbances",
        "snoring_minutes",
        "sleep_score",
    ])
    
    return sorted(metrics)
