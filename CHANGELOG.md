# Changelog

All notable changes to Resonance will be documented in this file.

## [0.1.0] - 2026-02-08

### Added

- Initial release
- Apple Health XML import (steps, sleep, heart rate, weight)
- Manual metric logging with notes and tags
- Spearman correlation analysis with lag support
- Weekday pattern detection (t-test)
- Anomaly detection (z-score)
- Week-over-week and month-over-month trends
- Report generation (text, JSON, Markdown formats)
- Natural language descriptions of findings
- CLI commands: ingest, log, analyze, report, status
- SQLite local storage
- TOML configuration with environment variable overrides

### Technical

- 171 tests passing
- Python 3.9+ support
- Dependencies: typer, rich, pandas, scipy, numpy
