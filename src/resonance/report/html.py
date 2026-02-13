"""HTML report generation with embedded visualizations."""

from dataclasses import dataclass
from typing import Optional
import html

import pandas as pd

from .generator import Report


def _generate_sparkline_svg(values: list[float], width: int = 100, height: int = 30) -> str:
    """Generate an inline SVG sparkline.
    
    Args:
        values: List of numeric values
        width: SVG width in pixels
        height: SVG height in pixels
        
    Returns:
        SVG markup string
    """
    if not values or len(values) < 2:
        return '<span style="color: #888;">-</span>'
    
    # Normalize values to fit in SVG
    min_val = min(values)
    max_val = max(values)
    val_range = max_val - min_val
    
    if val_range == 0:
        # Flat line
        y = height / 2
        points = " ".join(f"{i * width / (len(values) - 1)},{y}" for i in range(len(values)))
    else:
        points = []
        for i, v in enumerate(values):
            x = i * width / (len(values) - 1)
            y = height - ((v - min_val) / val_range) * (height - 4) - 2
            points.append(f"{x},{y}")
        points = " ".join(points)
    
    # Determine color based on trend
    if values[-1] > values[0]:
        color = "#22c55e"  # green
    elif values[-1] < values[0]:
        color = "#ef4444"  # red
    else:
        color = "#888888"  # gray
    
    return f'''<svg width="{width}" height="{height}" style="vertical-align: middle;">
        <polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>
    </svg>'''


def _generate_heatmap_cell(value: float) -> str:
    """Generate a heatmap cell with color based on correlation value.
    
    Args:
        value: Correlation coefficient (-1 to 1)
        
    Returns:
        HTML span with background color
    """
    # Map -1 to 1 to color: red(-1) -> white(0) -> blue(1)
    if value > 0:
        intensity = int(value * 200)
        color = f"rgb({255 - intensity}, {255 - intensity}, 255)"
    else:
        intensity = int(abs(value) * 200)
        color = f"rgb(255, {255 - intensity}, {255 - intensity})"
    
    return f'<span style="display: inline-block; width: 40px; height: 20px; background: {color}; text-align: center; font-size: 10px; line-height: 20px;">{value:.2f}</span>'


def format_html(
    report: Report,
    df: Optional[pd.DataFrame] = None,
    title: str = "Resonance Report"
) -> str:
    """Format report as self-contained HTML with charts.
    
    Args:
        report: Report to format
        df: Optional DataFrame for generating time series charts
        title: Page title
        
    Returns:
        Complete HTML document string
    """
    escaped_title = html.escape(title)
    
    # Build sections
    patterns_html = _build_patterns_section(report)
    weekday_html = _build_weekday_section(report)
    trends_html = _build_trends_section(report, df)
    quality_html = _build_quality_section(report)
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escaped_title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f8f9fa;
            color: #333;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        h1 {{
            color: #1a1a2e;
            margin-bottom: 5px;
        }}
        .subtitle {{
            color: #666;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 20px;
            margin-bottom: 20px;
        }}
        .card h2 {{
            color: #1a1a2e;
            font-size: 18px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            text-align: left;
            padding: 10px;
            border-bottom: 1px solid #eee;
        }}
        th {{
            color: #666;
            font-weight: 500;
            font-size: 12px;
            text-transform: uppercase;
        }}
        .correlation-positive {{ color: #22c55e; }}
        .correlation-negative {{ color: #ef4444; }}
        .trend-up {{ color: #22c55e; }}
        .trend-down {{ color: #ef4444; }}
        .trend-stable {{ color: #888; }}
        .confidence-high {{ background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 10px; font-size: 12px; }}
        .confidence-medium {{ background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 10px; font-size: 12px; }}
        .confidence-low {{ background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 10px; font-size: 12px; }}
        .progress-bar {{
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            background: #3b82f6;
            border-radius: 4px;
        }}
        .empty-state {{
            color: #888;
            font-style: italic;
            padding: 20px;
            text-align: center;
        }}
        .metric-pair {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .metric-pair span {{
            padding: 2px 8px;
            background: #f3f4f6;
            border-radius: 4px;
            font-size: 14px;
        }}
        footer {{
            text-align: center;
            color: #888;
            font-size: 12px;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{escaped_title}</h1>
        <p class="subtitle">Period: {html.escape(report.date_range[0])} to {html.escape(report.date_range[1])}</p>
        
        {patterns_html}
        {weekday_html}
        {trends_html}
        {quality_html}
        
        <footer>
            Generated by Resonance - Personal Pattern Discovery
        </footer>
    </div>
</body>
</html>'''


def _build_patterns_section(report: Report) -> str:
    """Build the correlations/patterns section."""
    if not report.patterns:
        return '''<div class="card">
            <h2>Correlations</h2>
            <p class="empty-state">No significant correlations found in this period.</p>
        </div>'''
    
    rows = []
    for p in report.patterns[:10]:  # Top 10
        corr_class = "correlation-positive" if p.correlation > 0 else "correlation-negative"
        conf_class = f"confidence-{p.confidence}"
        sign = "+" if p.correlation > 0 else ""
        
        rows.append(f'''<tr>
            <td>
                <div class="metric-pair">
                    <span>{html.escape(p.metric1)}</span>
                    <span style="color: #888;">↔</span>
                    <span>{html.escape(p.metric2)}</span>
                </div>
            </td>
            <td class="{corr_class}" style="font-weight: 600;">{sign}{p.correlation:.2f}</td>
            <td>{p.lag_days} days</td>
            <td><span class="{conf_class}">{html.escape(p.confidence)}</span></td>
        </tr>''')
    
    return f'''<div class="card">
        <h2>Correlations</h2>
        <table>
            <thead>
                <tr>
                    <th>Metrics</th>
                    <th>Correlation</th>
                    <th>Lag</th>
                    <th>Confidence</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>'''


def _build_weekday_section(report: Report) -> str:
    """Build the weekday patterns section."""
    if not report.weekday_effects:
        return '''<div class="card">
            <h2>Weekday Patterns</h2>
            <p class="empty-state">No significant weekday patterns found.</p>
        </div>'''
    
    rows = []
    for w in report.weekday_effects[:10]:
        direction = "higher" if w.difference_pct > 0 else "lower"
        color = "#22c55e" if w.difference_pct > 0 else "#ef4444"
        arrow = "↑" if w.difference_pct > 0 else "↓"
        
        rows.append(f'''<tr>
            <td><strong>{html.escape(w.weekday_name)}</strong></td>
            <td>{html.escape(w.metric)}</td>
            <td style="color: {color};">{arrow} {abs(w.difference_pct):.0f}% {direction}</td>
        </tr>''')
    
    return f'''<div class="card">
        <h2>Weekday Patterns</h2>
        <table>
            <thead>
                <tr>
                    <th>Day</th>
                    <th>Metric</th>
                    <th>Effect</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>'''


def _build_trends_section(report: Report, df: Optional[pd.DataFrame] = None) -> str:
    """Build the trends section with optional sparklines."""
    if not report.trends:
        return '''<div class="card">
            <h2>Trends</h2>
            <p class="empty-state">No trend data available.</p>
        </div>'''
    
    rows = []
    for t in report.trends:
        if t.direction == "stable":
            trend_class = "trend-stable"
            trend_text = "Stable"
            arrow = "→"
        elif t.direction == "up":
            trend_class = "trend-up"
            trend_text = f"+{abs(t.change_pct):.0f}%"
            arrow = "↑"
        else:
            trend_class = "trend-down"
            trend_text = f"-{abs(t.change_pct):.0f}%"
            arrow = "↓"
        
        # Generate sparkline if df is available
        sparkline = ""
        if df is not None and t.metric in df.columns:
            values = df[t.metric].dropna().tolist()[-14:]  # Last 14 days
            sparkline = _generate_sparkline_svg(values)
        
        rows.append(f'''<tr>
            <td>{html.escape(t.metric)}</td>
            <td>{sparkline}</td>
            <td class="{trend_class}" style="font-weight: 600;">{arrow} {trend_text}</td>
        </tr>''')
    
    return f'''<div class="card">
        <h2>Trends</h2>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Last 14 Days</th>
                    <th>Change</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>'''


def _build_quality_section(report: Report) -> str:
    """Build the data quality section with progress bars."""
    if not report.data_quality:
        return '''<div class="card">
            <h2>Data Quality</h2>
            <p class="empty-state">No data quality information available.</p>
        </div>'''
    
    rows = []
    for metric, (days, total) in report.data_quality.items():
        pct = (days / total) * 100 if total > 0 else 0
        
        rows.append(f'''<tr>
            <td>{html.escape(metric)}</td>
            <td>{days}/{total} days</td>
            <td>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {pct:.0f}%;"></div>
                </div>
            </td>
            <td style="text-align: right; color: #666;">{pct:.0f}%</td>
        </tr>''')
    
    return f'''<div class="card">
        <h2>Data Quality</h2>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Coverage</th>
                    <th style="width: 200px;">Progress</th>
                    <th style="width: 60px;"></th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>'''
