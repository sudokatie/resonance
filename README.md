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

- **Apple Health import** - Steps, sleep, heart rate, weight
- **Manual logging** - Mood, energy, custom metrics
- **Correlation analysis** - Find what affects what
- **Lagged effects** - Does X today affect Y tomorrow?
- **Weekday patterns** - Your Tuesday problem, quantified
- **Natural language reports** - Insights you can understand

## Privacy

All data stored locally in `~/.resonance/`. No network requests. Ever.

## License

MIT
