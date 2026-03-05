# Resonance

Find patterns in your life. Ingest data from health apps, calendar, and manual logs. Discover correlations you never noticed.

Your data stays on your machine. No cloud. No tracking. Just insights.

## Quick Start

```bash
# Install
pip install -e .

# Import Apple Health data
resonance ingest health ~/Downloads/export.xml

# Log your mood
resonance log mood 7 --note "Good day"

# Find patterns
resonance analyze

# Get a report
resonance report
```

## Features

- **Multiple data sources** - Apple Health, Google Fit, Fitbit, Oura Ring, Withings
- **Manual logging** - Mood, energy, custom metrics
- **Correlation analysis** - Find what affects what
- **Lagged effects** - Does X today affect Y tomorrow?
- **Weekday patterns** - Your Tuesday problem, quantified
- **Trend tracking** - Week-over-week, month-over-month
- **Natural language reports** - Insights you can understand
- **HTML reports** - Self-contained reports with sparkline charts and visualizations
- **Automated daily reports** - Scheduled delivery via email, file, or notification

## Installation

```bash
# Clone the repo
git clone https://github.com/sudokatie/resonance.git
cd resonance

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install
pip install -e .
```

## Usage

### Data Sources

Resonance supports multiple fitness and health data sources.

#### Apple Health

Export your data from the Health app on iPhone (Profile > Export All Health Data):

```bash
resonance ingest health ~/Downloads/export.xml
```

Imports: steps, distance, calories, sleep, heart rate, weight.

#### Google Fit

Requires OAuth setup. Create credentials at [Google Cloud Console](https://console.cloud.google.com/apis/credentials):

```bash
# First time - opens browser for authorization
resonance ingest google-fit --client-id YOUR_ID --client-secret YOUR_SECRET

# After authorization, credentials are saved
resonance ingest google-fit --days 30
```

Imports: steps, distance, calories, sleep, heart rate, weight.

#### Fitbit

Requires OAuth setup. Create an app at [Fitbit Developer](https://dev.fitbit.com/apps):

```bash
# First time - opens browser for authorization
resonance ingest fitbit --client-id YOUR_ID --client-secret YOUR_SECRET

# After authorization, credentials are saved
resonance ingest fitbit --days 30
```

Imports: steps, distance, calories, sleep, heart rate, weight.

#### Oura Ring

Get a personal access token from [Oura Cloud](https://cloud.ouraring.com/personal-access-tokens):

```bash
# First time - saves token for future use
resonance ingest oura --token YOUR_TOKEN

# After that, just specify days
resonance ingest oura --days 30
```

Imports: sleep metrics (hours, efficiency, deep/REM/light sleep, HRV), readiness score, temperature deviation, steps, calories, distance.

#### Withings

Register an app at [Withings Developer](https://developer.withings.com/) to get OAuth credentials:

```bash
# First time - opens browser for authorization
resonance ingest withings --client-id YOUR_ID --client-secret YOUR_SECRET

# After authorization, credentials are saved
resonance ingest withings --days 30
```

Imports: weight, blood pressure (systolic/diastolic), heart rate, body composition (fat ratio, muscle mass, hydration), sleep metrics (total, deep, light, REM, score, heart rate during sleep, breathing disturbances, snoring).

#### API Sources Dependencies

Google Fit, Fitbit, Oura, and Withings require the `httpx` library:

```bash
pip install "resonance[api]"
```

### Log Manual Metrics

```bash
# Basic logging
resonance log mood 7
resonance log energy 8

# With notes and tags
resonance log mood 6 --note "Tired after travel" --tags "travel,jet-lag"
```

### Analyze Patterns

```bash
# Find correlations
resonance analyze

# Limit to specific metrics
resonance analyze --metrics mood,sleep,steps

# Check for lagged effects (e.g., does X today affect Y tomorrow?)
resonance analyze --lag 2
```

### Generate Reports

```bash
# Weekly text report
resonance report

# Monthly JSON report
resonance report --period month --format json

# HTML report with charts
resonance report --format html --output ~/reports/weekly.html

# Save to file
resonance report --output ~/reports/weekly.md --format markdown
```

### TUI Dashboard

```bash
# Show interactive terminal dashboard
resonance dashboard

# Monthly view
resonance dashboard --period month

# Show correlation heatmap
resonance dashboard --heatmap
```

The dashboard displays:
- Patterns with color-coded correlations
- Weekday effects with significance indicators
- Trends with direction arrows
- Data quality metrics with progress bars

### Automated Daily Reports

```bash
# Generate and print daily report
resonance daily

# Save to file
resonance daily --delivery file

# Send via email (requires SMTP env vars)
resonance daily --delivery email

# Force generation even with limited data
resonance daily --force
```

Configure in `~/.config/resonance/config.toml`:

```toml
[daily]
enabled = true
delivery = "email"            # stdout, file, email, notification
email_to = "you@example.com"
min_data_days = 7
include_trends = true
include_correlations = true
include_weekday = true
```

For email delivery, set environment variables:
- `SMTP_HOST` - SMTP server hostname
- `SMTP_PORT` - SMTP port (default: 587)
- `SMTP_USER` - SMTP username
- `SMTP_PASS` - SMTP password
- `SMTP_FROM` - From address

Example cron entry for 8 AM daily:
```bash
0 8 * * * resonance daily --delivery email
```

### Check Status

```bash
resonance status
```

## Configuration

Configuration is stored in `~/.config/resonance/config.toml`:

```toml
[analysis]
min_days = 14
p_threshold = 0.05
min_correlation = 0.3
max_lag = 1

health_types = ["StepCount", "SleepAnalysis", "HeartRate", "BodyMass"]
```

Override with environment variables:
```bash
export RESONANCE_DB_PATH=~/mydata/resonance.db
```

## How It Works

1. **Data Ingestion** - Parse Apple Health XML, aggregate to daily metrics
2. **Manual Logging** - Add mood, energy, or any custom metric
3. **Correlation Analysis** - Spearman correlation with lag support
4. **Pattern Detection** - Weekday effects, anomalies, trends
5. **Reporting** - Natural language summaries of findings

### Confidence Levels

- **High** - 50+ samples, p < 0.01, |r| >= 0.5
- **Medium** - 30+ samples, p < 0.05, |r| >= 0.3
- **Low** - 14+ samples, p < 0.05, |r| >= 0.3

## Privacy

All data stored locally in `~/.resonance/`. No network requests. Ever.

Your patterns are your business.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=resonance
```

## License

MIT

---

*Your life has patterns. Resonance helps you find them.*
