"""Configuration loading with TOML, env vars, and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Use tomllib on Python 3.11+, tomli otherwise
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore


@dataclass
class AnalysisConfig:
    """Configuration for analysis parameters."""
    
    min_days: int = 14
    p_threshold: float = 0.05
    min_correlation: float = 0.3
    max_lag: int = 1


@dataclass
class ResonanceConfig:
    """Main configuration for Resonance."""
    
    db_path: Path = field(default_factory=lambda: Path.home() / ".resonance" / "data.db")
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    health_types: list[str] = field(default_factory=lambda: [
        "StepCount",
        "SleepAnalysis",
        "HeartRate",
        "BodyMass",
        "DistanceWalkingRunning",
        "ActiveEnergyBurned",
        "RestingHeartRate",
    ])


def get_default_config() -> ResonanceConfig:
    """Return default configuration."""
    return ResonanceConfig()


def get_config_path() -> Path:
    """Get the default config file path (XDG compliant)."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "resonance" / "config.toml"
    return Path.home() / ".config" / "resonance" / "config.toml"


def load_config(path: Path | None = None) -> ResonanceConfig:
    """Load config from file, env vars, and defaults.
    
    Priority (highest to lowest):
    1. Environment variables
    2. Config file
    3. Defaults
    """
    config = get_default_config()
    
    # Determine config file path
    if path is None:
        path = get_config_path()
    
    # Load from file if exists
    if path.exists():
        config = _merge_from_file(config, path)
    
    # Override from environment
    config = _override_from_env(config)
    
    # Ensure db parent directory exists
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    return config


def _merge_from_file(config: ResonanceConfig, path: Path) -> ResonanceConfig:
    """Merge configuration from TOML file."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    
    # Database path
    if "database" in data and "path" in data["database"]:
        db_path = data["database"]["path"]
        config.db_path = Path(db_path).expanduser()
    
    # Analysis config
    if "analysis" in data:
        analysis = data["analysis"]
        if "min_days" in analysis:
            config.analysis.min_days = int(analysis["min_days"])
        if "p_threshold" in analysis:
            config.analysis.p_threshold = float(analysis["p_threshold"])
        if "min_correlation" in analysis:
            config.analysis.min_correlation = float(analysis["min_correlation"])
        if "max_lag" in analysis:
            config.analysis.max_lag = int(analysis["max_lag"])
    
    # Health types
    if "import" in data and "health_types" in data["import"]:
        config.health_types = list(data["import"]["health_types"])
    
    return config


def _override_from_env(config: ResonanceConfig) -> ResonanceConfig:
    """Override configuration from environment variables."""
    if db_path := os.environ.get("RESONANCE_DB_PATH"):
        config.db_path = Path(db_path).expanduser()
    
    if min_days := os.environ.get("RESONANCE_MIN_DAYS"):
        config.analysis.min_days = int(min_days)
    
    if p_threshold := os.environ.get("RESONANCE_P_THRESHOLD"):
        config.analysis.p_threshold = float(p_threshold)
    
    if min_correlation := os.environ.get("RESONANCE_MIN_CORRELATION"):
        config.analysis.min_correlation = float(min_correlation)
    
    if max_lag := os.environ.get("RESONANCE_MAX_LAG"):
        config.analysis.max_lag = int(max_lag)
    
    return config


def validate_config(config: ResonanceConfig) -> list[str]:
    """Validate configuration values. Returns list of error messages."""
    errors = []
    
    if config.analysis.min_days < 1:
        errors.append("min_days must be at least 1")
    
    if not 0 < config.analysis.p_threshold <= 1:
        errors.append("p_threshold must be between 0 and 1")
    
    if not 0 < config.analysis.min_correlation <= 1:
        errors.append("min_correlation must be between 0 and 1")
    
    if config.analysis.max_lag < 0:
        errors.append("max_lag must be non-negative")
    
    return errors
