"""Tests for gmail_scan.py query building and state management."""
import importlib.util
import json
import sys
from pathlib import Path

# Load gmail_scan as a module without executing main()
spec = importlib.util.spec_from_file_location(
    "gmail_scan",
    Path(__file__).parent.parent / "scripts" / "gmail_scan.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_query_wraps_unread_or_attachment():
    """(is:unread OR has:attachment) must be parenthesized so it ANDs with the rest."""
    query = mod.build_gmail_query("2026/01/01", "2026/03/05")
    assert "(is:unread OR has:attachment)" in query


def test_query_excludes_forums_and_newsletters():
    """Query must include forums and newsletter exclusions."""
    query = mod.build_gmail_query("2026/01/01", "2026/03/05")
    assert "-category:forums" in query
    assert "-label:^smartlabel_newsletters" in query


def test_query_excludes_promotional_subjects():
    """Query must have a subject-based exclusion for marketing terms."""
    query = mod.build_gmail_query("2026/01/01", "2026/03/05")
    assert "-subject:" in query


def test_query_includes_subscription_renewal_terms():
    """Query must include subscription renewal as a positive signal."""
    query = mod.build_gmail_query("2026/01/01", "2026/03/05")
    assert "subscription renewal" in query or "auto-renew" in query


def test_load_state_returns_split_timestamp_keys():
    """load_state must return last_scan_started and last_scan_completed keys."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        state = mod.load_state(Path(d) / "state.json")
    assert "last_scan_started" in state
    assert "last_scan_completed" in state
    assert "last_run" not in state


def test_save_state_started_sets_only_started(tmp_path):
    """save_state_started sets last_scan_started but NOT last_scan_completed."""
    state_file = tmp_path / "state.json"
    state = mod.load_state(state_file)
    mod.save_state_started(state, state_file, "2026-03-05T10:00:00Z")
    saved = json.loads(state_file.read_text())
    assert saved["last_scan_started"] == "2026-03-05T10:00:00Z"
    assert saved.get("last_scan_completed") is None


def test_gmail_scan_output_uses_skill_chain(capsys, tmp_path):
    import gmail_scan
    gmail_scan.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "doc-radar:legal-doc-detector" in out
    assert "hash_check.py" not in out
    assert "doc-extractor skill" not in out
    assert "deadline-scheduler skill" not in out

def test_gmail_scan_warns_against_direct_scripts(capsys, tmp_path):
    import gmail_scan
    gmail_scan.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "DO NOT run scripts directly" in out

def test_gmail_scan_output_includes_rate_limit_guidance(capsys, tmp_path):
    import gmail_scan
    gmail_scan.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "429" in out or "rate limit" in out.lower()


def test_build_drive_query_contains_legal_name_terms():
    """Drive query must include legal document name signals."""
    query = mod.build_drive_query("2026-02-07")
    assert "contract" in query
    assert "invoice" in query
    assert "NDA" in query


def test_build_drive_query_filters_mime_types():
    """Drive query must restrict to PDF, DOCX, and plain text."""
    query = mod.build_drive_query("2026-02-07")
    assert "application/pdf" in query
    assert "openxmlformats" in query


def test_build_drive_query_excludes_trashed():
    query = mod.build_drive_query("2026-02-07")
    assert "trashed=false" in query


def test_build_drive_query_uses_after_date():
    query = mod.build_drive_query("2026-02-07")
    assert "2026-02-07" in query
    assert "modifiedTime" in query


def test_gmail_scan_output_includes_drive_section(capsys, tmp_path):
    import gmail_scan
    gmail_scan.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "Google Drive" in out
    assert "gws drive files list" in out


def test_gmail_scan_output_drive_source_is_google_drive(capsys, tmp_path):
    import gmail_scan
    gmail_scan.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "google_drive" in out
