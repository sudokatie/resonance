"""Tests for the interactive TUI logging module."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from resonance.tui import (
    COMMON_METRICS,
    show_metric_menu,
    show_today_entries,
    prompt_metric_entry,
    interactive_log,
    quick_log,
)
from resonance.database import Database
from resonance.ingest.manual import get_today_entries, delete_entry


@pytest.fixture
def db(tmp_path):
    """Create a temporary database."""
    db_path = tmp_path / "test.db"
    return Database(db_path)


class TestCommonMetrics:
    """Tests for common metrics definitions."""
    
    def test_common_metrics_exist(self):
        """Should have common metrics defined."""
        assert len(COMMON_METRICS) > 0
        assert "mood" in COMMON_METRICS
        assert "energy" in COMMON_METRICS
        assert "sleep" in COMMON_METRICS
    
    def test_common_metrics_have_ranges(self):
        """Each metric should have min, max, and desc."""
        for name, info in COMMON_METRICS.items():
            assert "min" in info, f"{name} missing min"
            assert "max" in info, f"{name} missing max"
            assert "desc" in info, f"{name} missing desc"
            assert info["min"] < info["max"], f"{name} min >= max"


class TestShowMetricMenu:
    """Tests for show_metric_menu function."""
    
    def test_show_metric_menu_no_errors(self, capsys):
        """Should display menu without errors."""
        show_metric_menu()
        captured = capsys.readouterr()
        # Rich output goes to stdout
        assert "mood" in captured.out.lower() or len(captured.out) > 0


class TestShowTodayEntries:
    """Tests for show_today_entries function."""
    
    def test_empty_entries(self, db, capsys):
        """Should handle empty entries gracefully."""
        entries = show_today_entries(db)
        assert entries == []
    
    def test_with_entries(self, db, capsys):
        """Should display logged entries."""
        from resonance.ingest.manual import log_metric
        log_metric(db, "mood", 7)
        log_metric(db, "energy", 6)
        
        entries = show_today_entries(db)
        assert len(entries) == 2


class TestGetTodayEntries:
    """Tests for get_today_entries function."""
    
    def test_empty_db(self, db):
        """Should return empty list for empty db."""
        entries = get_today_entries(db)
        assert entries == []
    
    def test_returns_todays_entries(self, db):
        """Should return only today's manual entries."""
        from resonance.ingest.manual import log_metric
        log_metric(db, "mood", 8)
        
        entries = get_today_entries(db)
        assert len(entries) == 1
        assert entries[0]["metric"] == "mood"
        assert entries[0]["value"] == 8
    
    def test_entry_has_required_fields(self, db):
        """Each entry should have id, metric, value, date."""
        from resonance.ingest.manual import log_metric
        log_metric(db, "stress", 5)
        
        entries = get_today_entries(db)
        entry = entries[0]
        assert "id" in entry
        assert "metric" in entry
        assert "value" in entry
        assert "date" in entry
        assert entry["date"] == date.today().isoformat()


class TestDeleteEntry:
    """Tests for delete_entry function."""
    
    def test_delete_existing_entry(self, db):
        """Should delete an existing entry."""
        from resonance.ingest.manual import log_metric
        log_metric(db, "mood", 7)
        
        entries = get_today_entries(db)
        assert len(entries) == 1
        
        result = delete_entry(db, entries[0]["id"])
        assert result is True
        
        entries_after = get_today_entries(db)
        assert len(entries_after) == 0
    
    def test_delete_nonexistent_entry(self, db):
        """Should return False for nonexistent entry."""
        result = delete_entry(db, 99999)
        assert result is False


class TestPromptMetricEntry:
    """Tests for prompt_metric_entry function."""
    
    @patch('resonance.tui.Prompt.ask')
    def test_quit_returns_false(self, mock_ask, db):
        """Entering 'q' should return False."""
        mock_ask.return_value = "q"
        result = prompt_metric_entry(db)
        assert result is False
    
    @patch('resonance.tui.Prompt.ask')
    def test_question_mark_shows_menu(self, mock_ask, db, capsys):
        """Entering '?' should show menu and return True."""
        mock_ask.return_value = "?"
        result = prompt_metric_entry(db)
        assert result is True


class TestInteractiveLog:
    """Tests for interactive_log function."""
    
    @patch('resonance.tui.Prompt.ask')
    def test_quit_action(self, mock_ask, db, capsys):
        """Should exit on quit action."""
        mock_ask.return_value = "quit"
        interactive_log(db)
        captured = capsys.readouterr()
        assert "Goodbye" in captured.out or len(captured.out) > 0


class TestQuickLog:
    """Tests for quick_log function."""
    
    @patch('resonance.tui.prompt_metric_entry')
    def test_exits_when_prompt_returns_false(self, mock_prompt, db, capsys):
        """Should exit when prompt returns False."""
        mock_prompt.return_value = False
        quick_log(db)
        mock_prompt.assert_called_once()
