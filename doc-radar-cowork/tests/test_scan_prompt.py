"""Tests for scan_prompt.py — MCP-native Gmail scan prompt generator."""
import importlib.util
import json
import sys
from pathlib import Path

# Load scan_prompt as a module without executing main()
spec = importlib.util.spec_from_file_location(
    "scan_prompt",
    Path(__file__).parent.parent / "scripts" / "scan_prompt.py"
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


def test_scan_prompt_output_uses_mcp_connector(capsys, tmp_path):
    """Output must instruct Claude to use search_messages (MCP), not gws CLI."""
    mod.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "search_messages" in out
    assert "gws" not in out


def test_scan_prompt_output_references_cowork_skill(capsys, tmp_path):
    """Output must invoke doc-radar-cowork:legal-doc-detector, not doc-radar."""
    mod.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "doc-radar-cowork:legal-doc-detector" in out


def test_scan_prompt_warns_against_direct_scripts(capsys, tmp_path):
    """Output must tell Claude not to run scripts directly."""
    mod.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "DO NOT run scripts directly" in out


def test_scan_prompt_output_includes_rate_limit_guidance(capsys, tmp_path):
    """Output must mention rate limit (429) handling."""
    mod.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "429" in out or "rate limit" in out.lower()


def test_scan_prompt_notes_attachment_limitation(capsys, tmp_path):
    """Output must document that attachment download is not available via MCP."""
    mod.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "attachment" in out.lower()
    # Must mention the limitation somewhere
    assert "not" in out.lower() or "limitation" in out.lower() or "no" in out.lower()
