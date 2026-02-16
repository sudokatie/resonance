"""Fitbit API integration.

Uses OAuth2 for authentication and REST API for data retrieval.
"""

from __future__ import annotations

import base64
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


# Fitbit API endpoints
AUTH_URL = "https://www.fitbit.com/oauth2/authorize"
TOKEN_URL = "https://api.fitbit.com/oauth2/token"
API_BASE = "https://api.fitbit.com/1/user/-"

# Scopes needed for fitness data
SCOPES = ["activity", "heartrate", "sleep", "weight"]

# Map Fitbit endpoints to metric names
# Format: (endpoint_path, json_key, metric_name, aggregation)
ENDPOINTS: list[tuple[str, str, str, str]] = [
    ("activities/steps/date/{start}/{end}.json", "activities-steps", "steps", "sum"),
    ("activities/distance/date/{start}/{end}.json", "activities-distance", "distance_km", "sum"),
    ("activities/calories/date/{start}/{end}.json", "activities-calories", "active_calories", "sum"),
    ("activities/heart/date/{start}/{end}.json", "activities-heart", "heart_rate_avg", "avg"),
    ("body/weight/date/{start}/{end}.json", "body-weight", "weight_kg", "last"),
    ("sleep/date/{date}.json", "sleep", "sleep_hours", "sum"),
]


@dataclass
class FitbitCredentials:
    """OAuth credentials for Fitbit."""
    
    access_token: str
    refresh_token: str
    expires_at: float
    client_id: str
    client_secret: str
    
    def is_expired(self) -> bool:
        """Check if access token is expired."""
        return time.time() >= self.expires_at - 60
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitbitCredentials:
        """Create from dictionary."""
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
            client_id=data["client_id"],
            client_secret=data["client_secret"],
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
            self.wfile.write(b"<html><body><h1>Fitbit authorization successful!</h1>")
            self.wfile.write(b"<p>You can close this window.</p></body></html>")
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            error = query.get("error_description", ["Unknown error"])[0]
            self.wfile.write(f"<html><body><h1>Error: {error}</h1></body></html>".encode())
    
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress log messages."""
        pass


def get_credentials_path() -> Path:
    """Get path to credentials file."""
    config_dir = Path.home() / ".config" / "resonance"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "fitbit_credentials.json"


def save_credentials(creds: FitbitCredentials) -> None:
    """Save credentials to file."""
    path = get_credentials_path()
    with open(path, "w") as f:
        json.dump(creds.to_dict(), f)


def load_credentials() -> FitbitCredentials | None:
    """Load credentials from file if they exist."""
    path = get_credentials_path()
    if not path.exists():
        return None
    
    try:
        with open(path) as f:
            data = json.load(f)
        return FitbitCredentials.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def get_basic_auth(client_id: str, client_secret: str) -> str:
    """Get Basic auth header for Fitbit token requests."""
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def refresh_access_token(creds: FitbitCredentials) -> FitbitCredentials:
    """Refresh access token using refresh token."""
    if httpx is None:
        raise ImportError("httpx is required for Fitbit integration")
    
    response = httpx.post(
        TOKEN_URL,
        headers={
            "Authorization": get_basic_auth(creds.client_id, creds.client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": creds.refresh_token,
        },
    )
    response.raise_for_status()
    data = response.json()
    
    new_creds = FitbitCredentials(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", creds.refresh_token),
        expires_at=time.time() + data.get("expires_in", 28800),
        client_id=creds.client_id,
        client_secret=creds.client_secret,
    )
    save_credentials(new_creds)
    return new_creds


def authenticate(
    client_id: str,
    client_secret: str,
    redirect_port: int = 8080,
) -> FitbitCredentials:
    """Perform OAuth2 flow to get credentials.
    
    Args:
        client_id: Fitbit OAuth client ID.
        client_secret: Fitbit OAuth client secret.
        redirect_port: Port for local redirect server.
        
    Returns:
        FitbitCredentials with access and refresh tokens.
    """
    if httpx is None:
        raise ImportError("httpx is required for Fitbit integration")
    
    redirect_uri = f"http://localhost:{redirect_port}"
    
    # Build authorization URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "expires_in": "604800",  # 7 days
    }
    auth_url = f"{AUTH_URL}?{urlencode(auth_params)}"
    
    # Start local server
    server = HTTPServer(("localhost", redirect_port), OAuthCallbackHandler)
    server.timeout = 120
    
    # Open browser
    webbrowser.open(auth_url)
    
    # Wait for callback
    OAuthCallbackHandler.auth_code = None
    while OAuthCallbackHandler.auth_code is None:
        server.handle_request()
    
    server.server_close()
    auth_code = OAuthCallbackHandler.auth_code
    
    # Exchange code for tokens
    response = httpx.post(
        TOKEN_URL,
        headers={
            "Authorization": get_basic_auth(client_id, client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    response.raise_for_status()
    data = response.json()
    
    creds = FitbitCredentials(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", ""),
        expires_at=time.time() + data.get("expires_in", 28800),
        client_id=client_id,
        client_secret=client_secret,
    )
    save_credentials(creds)
    return creds


def get_valid_credentials(
    client_id: str | None = None,
    client_secret: str | None = None,
) -> FitbitCredentials:
    """Get valid credentials, refreshing or re-authenticating as needed."""
    creds = load_credentials()
    
    if creds is None:
        if not client_id or not client_secret:
            raise ValueError(
                "No saved credentials. Provide client_id and client_secret for initial auth."
            )
        return authenticate(client_id, client_secret)
    
    if creds.is_expired():
        return refresh_access_token(creds)
    
    return creds


def fetch_time_series(
    creds: FitbitCredentials,
    endpoint: str,
    start_date: datetime,
    end_date: datetime,
) -> dict[str, Any]:
    """Fetch time series data from Fitbit API.
    
    Args:
        creds: Valid credentials.
        endpoint: Endpoint path template.
        start_date: Start of date range.
        end_date: End of date range.
        
    Returns:
        JSON response from API.
    """
    if httpx is None:
        raise ImportError("httpx is required for Fitbit integration")
    
    # Format dates
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Build URL
    path = endpoint.format(start=start_str, end=end_str, date=start_str)
    url = f"{API_BASE}/{path}"
    
    headers = {"Authorization": f"Bearer {creds.access_token}"}
    
    response = httpx.get(url, headers=headers, timeout=30.0)
    response.raise_for_status()
    return response.json()


def parse_time_series(
    data: dict[str, Any],
    json_key: str,
    metric_name: str,
) -> list[tuple[str, float]]:
    """Parse time series response to date/value pairs.
    
    Args:
        data: JSON response from API.
        json_key: Key to extract from response.
        metric_name: Name of metric.
        
    Returns:
        List of (date, value) tuples.
    """
    results: list[tuple[str, float]] = []
    
    items = data.get(json_key, [])
    
    for item in items:
        date_str = item.get("dateTime") or item.get("date")
        if not date_str:
            continue
        
        # Handle different value formats
        value = item.get("value")
        if value is None:
            # Heart rate has nested structure
            if "restingHeartRate" in item:
                value = item["restingHeartRate"]
            elif "value" in item:
                value = item["value"]
            else:
                continue
        
        try:
            value = float(value)
            results.append((date_str, value))
        except (ValueError, TypeError):
            continue
    
    return results


def parse_sleep_data(data: dict[str, Any]) -> list[tuple[str, float]]:
    """Parse sleep data to date/hours pairs.
    
    Args:
        data: JSON response from sleep endpoint.
        
    Returns:
        List of (date, hours) tuples.
    """
    results: list[tuple[str, float]] = []
    
    sleep_logs = data.get("sleep", [])
    
    for log in sleep_logs:
        date_str = log.get("dateOfSleep")
        if not date_str:
            continue
        
        # Get total sleep time in minutes
        minutes = log.get("minutesAsleep", 0)
        hours = minutes / 60
        
        if hours > 0:
            results.append((date_str, hours))
    
    return results


def import_fitbit(
    db: Database,
    days: int = 30,
    client_id: str | None = None,
    client_secret: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    console: Any = None,
) -> int:
    """Import data from Fitbit.
    
    Args:
        db: Database instance.
        days: Number of days to import.
        client_id: Fitbit OAuth client ID.
        client_secret: Fitbit OAuth client secret.
        dry_run: If True, don't actually insert.
        verbose: If True, log each metric.
        console: Rich console for output.
        
    Returns:
        Number of metrics imported.
    """
    if httpx is None:
        raise ImportError(
            "httpx is required for Fitbit integration. "
            "Install with: pip install httpx"
        )
    
    # Get credentials
    creds = get_valid_credentials(client_id, client_secret)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    metrics: list[MetricRecord] = []
    
    # Fetch each endpoint
    for endpoint, json_key, metric_name, _ in ENDPOINTS:
        if verbose and console:
            console.print(f"  Fetching {metric_name}...")
        
        try:
            # Sleep needs to be fetched day by day
            if metric_name == "sleep_hours":
                current = start_date
                while current <= end_date:
                    data = fetch_time_series(creds, endpoint, current, current)
                    for date_str, value in parse_sleep_data(data):
                        metrics.append(MetricRecord(
                            date=date_str,
                            metric_name=metric_name,
                            value=value,
                            source="fitbit",
                        ))
                        if verbose and console:
                            console.print(f"    {date_str}: {value:.2f}")
                    current += timedelta(days=1)
            else:
                data = fetch_time_series(creds, endpoint, start_date, end_date)
                for date_str, value in parse_time_series(data, json_key, metric_name):
                    metrics.append(MetricRecord(
                        date=date_str,
                        metric_name=metric_name,
                        value=value,
                        source="fitbit",
                    ))
                    if verbose and console:
                        console.print(f"    {date_str}: {value:.2f}")
        except Exception as e:
            if verbose and console:
                console.print(f"    Error: {e}", style="yellow")
    
    if dry_run:
        return len(metrics)
    
    return db.insert_metrics(metrics)


def get_supported_metrics() -> list[str]:
    """Get list of metric names we can import from Fitbit."""
    return sorted(set(metric for _, _, metric, _ in ENDPOINTS))
