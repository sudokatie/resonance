"""Tests for configuration loading."""

from pathlib import Path

from resonance.config import (
    ResonanceConfig,
    get_default_config,
    load_config,
    validate_config,
)


def test_get_default_config():
    """Default config has expected values."""
    config = get_default_config()
    assert isinstance(config, ResonanceConfig)
    assert config.analysis.min_days == 14
    assert config.analysis.p_threshold == 0.05
    assert config.analysis.min_correlation == 0.3
    assert config.analysis.max_lag == 1


def test_default_db_path():
    """Default database path is in home directory."""
    config = get_default_config()
    assert config.db_path == Path.home() / ".resonance" / "data.db"


def test_default_health_types():
    """Default health types include common metrics."""
    config = get_default_config()
    assert "StepCount" in config.health_types
    assert "SleepAnalysis" in config.health_types
    assert "HeartRate" in config.health_types


def test_load_config_no_file(temp_dir):
    """Load config returns defaults when no file exists."""
    config = load_config(temp_dir / "nonexistent.toml")
    assert config.analysis.min_days == 14


def test_load_config_from_toml(temp_dir):
    """Load config reads values from TOML file."""
    config_file = temp_dir / "config.toml"
    config_file.write_text("""
[database]
path = "~/custom/data.db"

[analysis]
min_days = 30
p_threshold = 0.01
""")
    config = load_config(config_file)
    assert config.db_path == Path.home() / "custom" / "data.db"
    assert config.analysis.min_days == 30
    assert config.analysis.p_threshold == 0.01


def test_env_var_overrides_file(temp_dir, monkeypatch):
    """Environment variables override file values."""
    config_file = temp_dir / "config.toml"
    config_file.write_text("""
[analysis]
min_days = 30
""")
    monkeypatch.setenv("RESONANCE_MIN_DAYS", "7")
    config = load_config(config_file)
    assert config.analysis.min_days == 7


def test_env_var_overrides_default(temp_dir, monkeypatch):
    """Environment variables override defaults."""
    monkeypatch.setenv("RESONANCE_DB_PATH", "/tmp/test.db")
    config = load_config(temp_dir / "nonexistent.toml")
    assert config.db_path == Path("/tmp/test.db")


def test_partial_toml_merges_with_defaults(temp_dir):
    """Partial TOML file merges with defaults."""
    config_file = temp_dir / "config.toml"
    config_file.write_text("""
[analysis]
min_days = 30
""")
    config = load_config(config_file)
    assert config.analysis.min_days == 30
    # Other values should be defaults
    assert config.analysis.p_threshold == 0.05
    assert config.analysis.max_lag == 1


def test_validate_config_valid():
    """Valid config returns no errors."""
    config = get_default_config()
    errors = validate_config(config)
    assert errors == []


def test_validate_config_invalid_min_days():
    """Invalid min_days returns error."""
    config = get_default_config()
    config.analysis.min_days = 0
    errors = validate_config(config)
    assert any("min_days" in e for e in errors)


def test_validate_config_invalid_p_threshold():
    """Invalid p_threshold returns error."""
    config = get_default_config()
    config.analysis.p_threshold = 1.5
    errors = validate_config(config)
    assert any("p_threshold" in e for e in errors)


def test_resonance_config_env_var(temp_dir, monkeypatch):
    """RESONANCE_CONFIG env var overrides default config path."""
    config_file = temp_dir / "custom_config.toml"
    config_file.write_text("""
[analysis]
min_days = 99
""")
    monkeypatch.setenv("RESONANCE_CONFIG", str(config_file))
    config = load_config()  # No path argument - should use env var
    assert config.analysis.min_days == 99
