"""Google Fit API integration.

Uses OAuth2 for authentication and REST API for data retrieval.
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


# Google Fit API endpoints
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
FITNESS_API_BASE = "https://www.googleapis.com/fitness/v1/users/me"

# Scopes needed for fitness data
SCOPES = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.sleep.read",
]

# Map Google Fit data types to metric names
# Format: (data_type_name, metric_name, aggregation)
DATA_TYPE_MAP: dict[str, tuple[str, str]] = {
    "com.google.step_count.delta": ("steps", "sum"),
    "com.google.distance.delta": ("distance_km", "sum"),
    "com.google.calories.expended": ("active_calories", "sum"),
    "com.google.heart_rate.bpm": ("heart_rate_avg", "avg"),
    "com.google.weight": ("weight_kg", "last"),
    "com.google.sleep.segment": ("sleep_hours", "sum"),
}

# Sleep stages that count as actual sleep
SLEEP_STAGES = {1, 2, 3, 4, 5}  # Light, Deep, REM, Awake (in bed counts), Other


@dataclass
class GoogleFitCredentials:
    """OAuth credentials for Google Fit."""
    
    access_token: str
    refresh_token: str
    expires_at: float
    client_id: str
    client_secret: str
    
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
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoogleFitCredentials:
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
            self.wfile.write(b"<html><body><h1>Authorization successful!</h1>")
            self.wfile.write(b"<p>You can close this window.</p></body></html>")
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            error = query.get("error", ["Unknown error"])[0]
            self.wfile.write(f"<html><body><h1>Error: {error}</h1></body></html>".encode())
    
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress log messages."""
        pass


def get_credentials_path() -> Path:
    """Get path to credentials file."""
    config_dir = Path.home() / ".config" / "resonance"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "google_fit_credentials.json"


def save_credentials(creds: GoogleFitCredentials) -> None:
    """Save credentials to file."""
    path = get_credentials_path()
    with open(path, "w") as f:
        json.dump(creds.to_dict(), f)


def load_credentials() -> GoogleFitCredentials | None:
    """Load credentials from file if they exist."""
    path = get_credentials_path()
    if not path.exists():
        return None
    
    try:
        with open(path) as f:
            data = json.load(f)
        return GoogleFitCredentials.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def refresh_access_token(creds: GoogleFitCredentials) -> GoogleFitCredentials:
    """Refresh access token using refresh token."""
    if httpx is None:
        raise ImportError("httpx is required for Google Fit integration")
    
    response = httpx.post(
        TOKEN_URL,
        data={
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "refresh_token": creds.refresh_token,
            "grant_type": "refresh_token",
        },
    )
    response.raise_for_status()
    data = response.json()
    
    new_creds = GoogleFitCredentials(
        access_token=data["access_token"],
        refresh_token=creds.refresh_token,  # Keep existing refresh token
        expires_at=time.time() + data.get("expires_in", 3600),
        client_id=creds.client_id,
        client_secret=creds.client_secret,
    )
    save_credentials(new_creds)
    return new_creds


def authenticate(
    client_id: str,
    client_secret: str,
    redirect_port: int = 8080,
) -> GoogleFitCredentials:
    """Perform OAuth2 flow to get credentials.
    
    Opens browser for user to authorize, starts local server to receive callback.
    
    Args:
        client_id: Google OAuth client ID.
        client_secret: Google OAuth client secret.
        redirect_port: Port for local redirect server.
        
    Returns:
        GoogleFitCredentials with access and refresh tokens.
    """
    if httpx is None:
        raise ImportError("httpx is required for Google Fit integration")
    
    redirect_uri = f"http://localhost:{redirect_port}"
    
    # Build authorization URL
    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{AUTH_URL}?{urlencode(auth_params)}"
    
    # Start local server to receive callback
    server = HTTPServer(("localhost", redirect_port), OAuthCallbackHandler)
    server.timeout = 120  # 2 minute timeout
    
    # Open browser for authorization
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
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    response.raise_for_status()
    data = response.json()
    
    creds = GoogleFitCredentials(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", ""),
        expires_at=time.time() + data.get("expires_in", 3600),
        client_id=client_id,
        client_secret=client_secret,
    )
    save_credentials(creds)
    return creds


def get_valid_credentials(
    client_id: str | None = None,
    client_secret: str | None = None,
) -> GoogleFitCredentials:
    """Get valid credentials, refreshing or re-authenticating as needed.
    
    Args:
        client_id: Google OAuth client ID (needed for fresh auth).
        client_secret: Google OAuth client secret (needed for fresh auth).
        
    Returns:
        Valid GoogleFitCredentials.
    """
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


def fetch_fitness_data(
    creds: GoogleFitCredentials,
    data_type: str,
    start_time: datetime,
    end_time: datetime,
) -> list[dict[str, Any]]:
    """Fetch fitness data from Google Fit API.
    
    Args:
        creds: Valid credentials.
        data_type: Google Fit data type name.
        start_time: Start of date range.
        end_time: End of date range.
        
    Returns:
        List of data points from API.
    """
    if httpx is None:
        raise ImportError("httpx is required for Google Fit integration")
    
    # Convert to nanoseconds since epoch
    start_ns = int(start_time.timestamp() * 1e9)
    end_ns = int(end_time.timestamp() * 1e9)
    
    url = f"{FITNESS_API_BASE}/dataSources/derived:{data_type}:com.google.android.gms:merge_step_deltas/datasets/{start_ns}-{end_ns}"
    
    # Try different data source prefixes
    prefixes = [
        f"derived:{data_type}:com.google.android.gms:merge_step_deltas",
        f"derived:{data_type}:com.google.android.gms:estimated_steps",
        f"derived:{data_type}:com.google.android.gms:from_activities",
        f"raw:{data_type}",
    ]
    
    headers = {"Authorization": f"Bearer {creds.access_token}"}
    
    for prefix in prefixes:
        url = f"{FITNESS_API_BASE}/dataSources/{prefix}/datasets/{start_ns}-{end_ns}"
        try:
            response = httpx.get(url, headers=headers, timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("point"):
                    return data["point"]
        except httpx.HTTPError:
            continue
    
    return []


def aggregate_to_daily(
    data_points: list[dict[str, Any]],
    data_type: str,
) -> dict[str, float]:
    """Aggregate data points to daily values.
    
    Args:
        data_points: Raw data points from API.
        data_type: Data type name for aggregation method.
        
    Returns:
        Dict mapping date strings to aggregated values.
    """
    if data_type not in DATA_TYPE_MAP:
        return {}
    
    metric_name, agg_method = DATA_TYPE_MAP[data_type]
    daily: dict[str, list[float]] = {}
    
    for point in data_points:
        # Convert nanoseconds to datetime
        start_ns = int(point.get("startTimeNanos", 0))
        dt = datetime.fromtimestamp(start_ns / 1e9)
        date_str = dt.date().isoformat()
        
        # Extract value
        values = point.get("value", [])
        if not values:
            continue
        
        # Handle different value types
        value = values[0].get("fpVal") or values[0].get("intVal", 0)
        
        # Special handling for sleep segments
        if data_type == "com.google.sleep.segment":
            sleep_stage = values[0].get("intVal", 0)
            if sleep_stage not in SLEEP_STAGES:
                continue
            # Convert duration to hours
            end_ns = int(point.get("endTimeNanos", start_ns))
            value = (end_ns - start_ns) / 1e9 / 3600
        
        # Convert distance to km
        if data_type == "com.google.distance.delta":
            value = value / 1000  # meters to km
        
        if date_str not in daily:
            daily[date_str] = []
        daily[date_str].append(float(value))
    
    # Apply aggregation
    result: dict[str, float] = {}
    for date_str, values in daily.items():
        if agg_method == "sum":
            result[date_str] = sum(values)
        elif agg_method == "avg":
            result[date_str] = sum(values) / len(values)
        elif agg_method == "last":
            result[date_str] = values[-1]
        else:
            result[date_str] = sum(values)
    
    return result


def import_google_fit(
    db: Database,
    days: int = 30,
    client_id: str | None = None,
    client_secret: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    console: Any = None,
) -> int:
    """Import data from Google Fit.
    
    Args:
        db: Database instance.
        days: Number of days to import.
        client_id: Google OAuth client ID.
        client_secret: Google OAuth client secret.
        dry_run: If True, don't actually insert.
        verbose: If True, log each metric.
        console: Rich console for output.
        
    Returns:
        Number of metrics imported.
    """
    if httpx is None:
        raise ImportError(
            "httpx is required for Google Fit integration. "
            "Install with: pip install httpx"
        )
    
    # Get credentials
    creds = get_valid_credentials(client_id, client_secret)
    
    # Calculate date range
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    metrics: list[MetricRecord] = []
    
    # Fetch each data type
    for data_type, (metric_name, _) in DATA_TYPE_MAP.items():
        if verbose and console:
            console.print(f"  Fetching {metric_name}...")
        
        try:
            data_points = fetch_fitness_data(creds, data_type, start_time, end_time)
            daily_values = aggregate_to_daily(data_points, data_type)
            
            for date_str, value in daily_values.items():
                metrics.append(MetricRecord(
                    date=date_str,
                    metric_name=metric_name,
                    value=value,
                    source="google_fit",
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
    """Get list of metric names we can import from Google Fit."""
    return sorted(set(name for name, _ in DATA_TYPE_MAP.values()))
