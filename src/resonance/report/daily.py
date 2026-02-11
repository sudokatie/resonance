"""Automated daily report generation and delivery."""

from __future__ import annotations

import os
import smtplib
import subprocess
from dataclasses import dataclass
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Literal, Optional

from ..config import load_config, get_config_path
from ..database import Database
from .generator import Report, generate_report, format_text, format_markdown


@dataclass
class DailyReportConfig:
    """Configuration for daily reports.
    
    Attributes:
        enabled: Whether daily reports are enabled.
        delivery: How to deliver the report.
        email_to: Email recipient(s) for email delivery.
        email_subject: Email subject template.
        include_trends: Include trend analysis.
        include_correlations: Include correlation analysis.
        include_weekday: Include weekday patterns.
        min_data_days: Minimum days of data required to send report.
    """
    
    enabled: bool = False
    delivery: Literal["email", "file", "stdout", "notification"] = "stdout"
    email_to: Optional[str] = None
    email_subject: str = "Resonance Daily Report - {date}"
    include_trends: bool = True
    include_correlations: bool = True
    include_weekday: bool = True
    min_data_days: int = 7


def load_daily_config() -> DailyReportConfig:
    """Load daily report config from TOML config file.
    
    Returns:
        DailyReportConfig with settings from config file.
    """
    # Use tomllib on Python 3.11+, tomli otherwise
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore
    
    config_path = get_config_path()
    daily_dict: dict = {}
    
    if config_path.exists():
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
            daily_dict = data.get("daily", {})
    
    return DailyReportConfig(
        enabled=daily_dict.get("enabled", False),
        delivery=daily_dict.get("delivery", "stdout"),
        email_to=daily_dict.get("email_to"),
        email_subject=daily_dict.get("email_subject", "Resonance Daily Report - {date}"),
        include_trends=daily_dict.get("include_trends", True),
        include_correlations=daily_dict.get("include_correlations", True),
        include_weekday=daily_dict.get("include_weekday", True),
        min_data_days=daily_dict.get("min_data_days", 7),
    )


def generate_daily_report(
    db: Database,
    reference_date: Optional[date] = None,
    config: Optional[DailyReportConfig] = None,
) -> Optional[Report]:
    """Generate a daily report if enough data is available.
    
    Args:
        db: Database instance.
        reference_date: Date to generate report for (defaults to today).
        config: Daily report config (loads from file if not provided).
        
    Returns:
        Report if sufficient data, None otherwise.
    """
    if config is None:
        config = load_daily_config()
    
    report = generate_report(db, period="week", reference_date=reference_date)
    
    # Check if we have enough data
    total_data_days = sum(
        days for days, _ in report.data_quality.values()
    )
    if total_data_days < config.min_data_days:
        return None
    
    # Filter report sections based on config
    if not config.include_trends:
        report.trends = []
    if not config.include_correlations:
        report.patterns = []
    if not config.include_weekday:
        report.weekday_effects = []
    
    return report


def deliver_report(
    report: Report,
    config: Optional[DailyReportConfig] = None,
) -> bool:
    """Deliver the daily report via configured method.
    
    Args:
        report: The report to deliver.
        config: Delivery config (loads from file if not provided).
        
    Returns:
        True if delivery succeeded, False otherwise.
    """
    if config is None:
        config = load_daily_config()
    
    if config.delivery == "stdout":
        return _deliver_stdout(report)
    elif config.delivery == "file":
        return _deliver_file(report)
    elif config.delivery == "email":
        return _deliver_email(report, config)
    elif config.delivery == "notification":
        return _deliver_notification(report)
    else:
        return False


def _deliver_stdout(report: Report) -> bool:
    """Print report to stdout."""
    print(format_text(report))
    return True


def _deliver_file(report: Report) -> bool:
    """Write report to a dated file."""
    today = date.today().isoformat()
    config_dir = Path.home() / ".config" / "resonance" / "reports"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = config_dir / f"report-{today}.md"
    filepath.write_text(format_markdown(report))
    
    return True


def _deliver_email(report: Report, config: DailyReportConfig) -> bool:
    """Send report via email using SMTP."""
    if not config.email_to:
        return False
    
    # Get SMTP settings from environment
    smtp_host = os.environ.get("SMTP_HOST", "localhost")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user or "resonance@localhost")
    
    today = date.today().isoformat()
    subject = config.email_subject.format(date=today)
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = config.email_to
    
    # Plain text and HTML versions
    text_content = format_text(report)
    html_content = _markdown_to_html(format_markdown(report))
    
    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))
    
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_user and smtp_pass:
                server.starttls()
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, config.email_to.split(","), msg.as_string())
        return True
    except Exception:
        return False


def _deliver_notification(report: Report) -> bool:
    """Send report via system notification (macOS only for now)."""
    # Build a short summary for notification
    summary_parts = []
    
    if report.trends:
        up = sum(1 for t in report.trends if t.direction == "up")
        down = sum(1 for t in report.trends if t.direction == "down")
        if up or down:
            summary_parts.append(f"Trends: {up}↑ {down}↓")
    
    if report.patterns:
        summary_parts.append(f"{len(report.patterns)} correlations")
    
    if report.weekday_effects:
        summary_parts.append(f"{len(report.weekday_effects)} weekday patterns")
    
    summary = ", ".join(summary_parts) if summary_parts else "No significant patterns"
    
    # Use osascript on macOS
    try:
        script = f'''
        display notification "{summary}" with title "Resonance Daily Report"
        '''
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        return True
    except Exception:
        return False


def _markdown_to_html(md: str) -> str:
    """Simple markdown to HTML conversion for email."""
    import re
    
    html = md
    
    # Headers
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    
    # Bold
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    
    # Tables (simplified)
    lines = html.split("\n")
    in_table = False
    table_html = []
    result = []
    
    for line in lines:
        if line.startswith("|") and "|" in line[1:]:
            if not in_table:
                in_table = True
                table_html = ["<table border='1' cellpadding='5'>"]
            
            if line.strip().replace("|", "").replace("-", "").strip() == "":
                continue  # Skip separator row
            
            cells = [c.strip() for c in line.split("|")[1:-1]]
            row = "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
            table_html.append(row)
        else:
            if in_table:
                table_html.append("</table>")
                result.append("\n".join(table_html))
                in_table = False
                table_html = []
            
            # List items
            if line.startswith("- "):
                result.append(f"<li>{line[2:]}</li>")
            else:
                result.append(line)
    
    if in_table:
        table_html.append("</table>")
        result.append("\n".join(table_html))
    
    html = "\n".join(result)
    html = f"<html><body style='font-family: sans-serif;'>{html}</body></html>"
    
    return html


def run_daily(
    db_path: Optional[str] = None,
    delivery: Optional[str] = None,
    force: bool = False,
) -> bool:
    """Run the daily report generation and delivery.
    
    Args:
        db_path: Path to database (uses default if not provided).
        delivery: Override delivery method.
        force: Generate even if not enough data.
        
    Returns:
        True if report was generated and delivered.
    """
    config = load_daily_config()
    
    if delivery:
        config.delivery = delivery
    
    if force:
        config.min_data_days = 0
    
    db = Database(db_path)
    report = generate_daily_report(db, config=config)
    
    if report is None:
        return False
    
    return deliver_report(report, config)
