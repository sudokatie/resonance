"""SQLite database operations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .models import MetricRecord, PatternRecord, EventRecord


class Database:
    """SQLite database for storing metrics, patterns, and events."""
    
    def __init__(self, path: Path):
        """Initialize database connection.
        
        Args:
            path: Path to SQLite database file.
        """
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.init_schema()
    
    def init_schema(self) -> None:
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, metric_name)
            );
            
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY,
                metric1 TEXT NOT NULL,
                metric2 TEXT NOT NULL,
                correlation REAL NOT NULL,
                p_value REAL NOT NULL,
                lag_days INTEGER DEFAULT 0,
                sample_size INTEGER NOT NULL,
                confidence TEXT NOT NULL,
                discovered_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                value REAL,
                note TEXT,
                tags TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_metrics_date ON metrics(date);
            CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name);
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
        """)
        self.conn.commit()
    
    def close(self) -> None:
        """Close database connection."""
        self.conn.close()
    
    def insert_metric(self, date: str, name: str, value: float, source: str) -> None:
        """Insert or update a single metric value.
        
        Args:
            date: Date in YYYY-MM-DD format.
            name: Metric name (e.g., 'steps', 'mood').
            value: Numeric value.
            source: Data source (e.g., 'apple_health', 'manual').
        """
        self.conn.execute(
            "INSERT OR REPLACE INTO metrics (date, metric_name, value, source) VALUES (?, ?, ?, ?)",
            (date, name, value, source)
        )
        self.conn.commit()
    
    def insert_metrics(self, metrics: list[MetricRecord]) -> int:
        """Bulk insert metrics.
        
        Args:
            metrics: List of MetricRecord objects.
            
        Returns:
            Number of records inserted.
        """
        if not metrics:
            return 0
        
        self.conn.executemany(
            "INSERT OR REPLACE INTO metrics (date, metric_name, value, source) VALUES (?, ?, ?, ?)",
            [(m.date, m.metric_name, m.value, m.source) for m in metrics]
        )
        self.conn.commit()
        return len(metrics)
    
    def get_metrics(
        self,
        name: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        source: str | None = None,
    ) -> list[MetricRecord]:
        """Query metrics with optional filters.
        
        Args:
            name: Filter by metric name.
            from_date: Filter by start date (inclusive).
            to_date: Filter by end date (inclusive).
            source: Filter by source (e.g., 'manual', 'health').
            
        Returns:
            List of MetricRecord objects.
        """
        query = "SELECT rowid as id, date, metric_name, value, source FROM metrics WHERE 1=1"
        params: list = []
        
        if name:
            query += " AND metric_name = ?"
            params.append(name)
        if from_date:
            query += " AND date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND date <= ?"
            params.append(to_date)
        if source:
            query += " AND source = ?"
            params.append(source)
        
        query += " ORDER BY date"
        
        cursor = self.conn.execute(query, params)
        return [
            MetricRecord(
                date=row["date"],
                metric_name=row["metric_name"],
                value=row["value"],
                source=row["source"],
                id=row["id"],
            )
            for row in cursor
        ]
    
    def delete_metric(self, row_id: int) -> bool:
        """Delete a metric by its row ID.
        
        Args:
            row_id: SQLite rowid of the metric.
            
        Returns:
            True if deleted, False if not found.
        """
        cursor = self.conn.execute(
            "DELETE FROM metrics WHERE rowid = ?",
            (row_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_metrics_df(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> pd.DataFrame:
        """Get metrics as a DataFrame with date index and metric columns.
        
        Args:
            from_date: Filter by start date (inclusive).
            to_date: Filter by end date (inclusive).
            
        Returns:
            DataFrame with date as index and metrics as columns.
        """
        query = "SELECT date, metric_name, value FROM metrics WHERE 1=1"
        params: list = []
        
        if from_date:
            query += " AND date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND date <= ?"
            params.append(to_date)
        
        query += " ORDER BY date"
        
        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            return pd.DataFrame()
        
        # Pivot to wide format
        df = pd.DataFrame(rows, columns=["date", "metric_name", "value"])
        df = df.pivot(index="date", columns="metric_name", values="value")
        df.index = pd.to_datetime(df.index)
        return df
    
    def get_metric_names(self) -> list[str]:
        """Get list of all metric names in database.
        
        Returns:
            Sorted list of unique metric names.
        """
        cursor = self.conn.execute(
            "SELECT DISTINCT metric_name FROM metrics ORDER BY metric_name"
        )
        return [row[0] for row in cursor]
    
    def get_date_range(self, metric: str | None = None) -> tuple[str, str] | None:
        """Get earliest and latest dates for metric(s).
        
        Args:
            metric: Optional metric name to filter by.
            
        Returns:
            Tuple of (earliest_date, latest_date) or None if no data.
        """
        if metric:
            cursor = self.conn.execute(
                "SELECT MIN(date), MAX(date) FROM metrics WHERE metric_name = ?",
                (metric,)
            )
        else:
            cursor = self.conn.execute("SELECT MIN(date), MAX(date) FROM metrics")
        
        row = cursor.fetchone()
        if row and row[0] and row[1]:
            return (row[0], row[1])
        return None
    
    def insert_pattern(self, pattern: PatternRecord) -> None:
        """Store a discovered pattern.
        
        Args:
            pattern: PatternRecord to store.
        """
        self.conn.execute(
            """INSERT INTO patterns 
               (metric1, metric2, correlation, p_value, lag_days, sample_size, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                pattern.metric1,
                pattern.metric2,
                pattern.correlation,
                pattern.p_value,
                pattern.lag_days,
                pattern.sample_size,
                pattern.confidence,
            )
        )
        self.conn.commit()
    
    def get_patterns(self, min_confidence: str | None = None) -> list[PatternRecord]:
        """Query stored patterns.
        
        Args:
            min_confidence: Minimum confidence level ('low', 'medium', 'high').
            
        Returns:
            List of PatternRecord objects.
        """
        query = "SELECT metric1, metric2, correlation, p_value, lag_days, sample_size, confidence FROM patterns"
        params: list = []
        
        if min_confidence:
            confidence_order = {"low": 1, "medium": 2, "high": 3}
            min_level = confidence_order.get(min_confidence, 0)
            levels = [k for k, v in confidence_order.items() if v >= min_level]
            if levels:
                placeholders = ",".join("?" * len(levels))
                query += f" WHERE confidence IN ({placeholders})"
                params.extend(levels)
        
        query += " ORDER BY ABS(correlation) DESC"
        
        cursor = self.conn.execute(query, params)
        return [
            PatternRecord(
                metric1=row["metric1"],
                metric2=row["metric2"],
                correlation=row["correlation"],
                p_value=row["p_value"],
                lag_days=row["lag_days"],
                sample_size=row["sample_size"],
                confidence=row["confidence"],
            )
            for row in cursor
        ]
    
    def insert_event(self, event: EventRecord) -> None:
        """Insert a manual event/log.
        
        Args:
            event: EventRecord to store.
        """
        tags_str = ",".join(event.tags) if event.tags else None
        self.conn.execute(
            "INSERT INTO events (timestamp, event_type, value, note, tags) VALUES (?, ?, ?, ?, ?)",
            (event.timestamp, event.event_type, event.value, event.note, tags_str)
        )
        self.conn.commit()
    
    def get_events(
        self,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[EventRecord]:
        """Query events.
        
        Args:
            from_date: Filter by start date (inclusive).
            to_date: Filter by end date (inclusive).
            
        Returns:
            List of EventRecord objects.
        """
        query = "SELECT timestamp, event_type, value, note, tags FROM events WHERE 1=1"
        params: list = []
        
        if from_date:
            query += " AND timestamp >= ?"
            params.append(from_date)
        if to_date:
            query += " AND timestamp <= ?"
            params.append(to_date + "T23:59:59")
        
        query += " ORDER BY timestamp"
        
        cursor = self.conn.execute(query, params)
        return [
            EventRecord(
                timestamp=row["timestamp"],
                event_type=row["event_type"],
                value=row["value"],
                note=row["note"],
                tags=row["tags"].split(",") if row["tags"] else [],
            )
            for row in cursor
        ]
    
    def get_metric_count(self, metric: str | None = None) -> int:
        """Get count of metric records.
        
        Args:
            metric: Optional metric name to filter by.
            
        Returns:
            Number of records.
        """
        if metric:
            cursor = self.conn.execute(
                "SELECT COUNT(*) FROM metrics WHERE metric_name = ?", (metric,)
            )
        else:
            cursor = self.conn.execute("SELECT COUNT(*) FROM metrics")
        return cursor.fetchone()[0]

    def get_last_analysis_date(self) -> str | None:
        """Get the timestamp of the most recent analysis.
        
        Returns:
            ISO timestamp string or None if no analyses exist.
        """
        cursor = self.conn.execute(
            "SELECT MAX(discovered_at) FROM patterns"
        )
        row = cursor.fetchone()
        if row and row[0]:
            # Format as date/time without microseconds
            return row[0][:16].replace("T", " ")
        return None
