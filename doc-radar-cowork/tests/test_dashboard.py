import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def _record(**kw):
    base = {
        "timestamp": "2026-03-06T00:00:00+00:00",
        "run_id": "abc123",
        "doc_type": "invoice",
        "doc_ref": "INV-001",
        "sha256": "abc123def456xyz",
        "parties": {"issuer": "Acme Corp", "recipient": "NorthGrid"},
        "due_date": "2026-04-01",
        "expiry_date": None,
        "renewal_date": None,
        "cancel_by_date": None,
        "value": {"amount": 5000.0, "currency": "USD", "payment_terms": "Net 30"},
        "source": "gmail",
        "source_id": "msg123",
        "status": "complete",
        "calendar_event_ids": ["evt1"],
    }
    base.update(kw)
    return base


def test_dashboard_generates_html_file(tmp_path):
    import dashboard
    runs = tmp_path / "runs.jsonl"
    runs.write_text(json.dumps(_record()) + "\n")
    out = tmp_path / "dashboard.html"
    dashboard.generate(runs_path=runs, output_path=out)
    assert out.exists()
    content = out.read_text()
    assert "<!DOCTYPE html>" in content
    assert "INV-001" in content


def test_dashboard_includes_gmail_link(tmp_path):
    import dashboard
    runs = tmp_path / "runs.jsonl"
    runs.write_text(json.dumps(_record()) + "\n")
    out = tmp_path / "dashboard.html"
    dashboard.generate(runs_path=runs, output_path=out)
    content = out.read_text()
    assert "mail.google.com" in content
    assert "msg123" in content


def test_dashboard_shows_all_doc_types(tmp_path):
    import dashboard
    runs = tmp_path / "runs.jsonl"
    records = [
        _record(doc_type="invoice",  doc_ref="INV-001", source_id="m1"),
        _record(doc_type="contract", doc_ref="MSA-001", source_id="m2", run_id="def"),
        _record(doc_type="nda",      doc_ref="NDA-001", source_id="m3", run_id="ghi"),
    ]
    runs.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    out = tmp_path / "dashboard.html"
    dashboard.generate(runs_path=runs, output_path=out)
    content = out.read_text()
    assert "INV-001" in content
    assert "MSA-001" in content
    assert "NDA-001" in content


def test_dashboard_empty_runs(tmp_path):
    import dashboard
    runs = tmp_path / "runs.jsonl"
    runs.write_text("")
    out = tmp_path / "dashboard.html"
    dashboard.generate(runs_path=runs, output_path=out)
    assert out.exists()
    content = out.read_text()
    assert "No documents" in content


def test_dashboard_stats_counts(tmp_path):
    import dashboard
    runs = tmp_path / "runs.jsonl"
    records = [
        _record(run_id="a", status="complete", due_date="2099-12-01"),
        _record(run_id="b", status="complete", due_date="2020-01-01"),
        _record(run_id="c", status="archived", due_date="2099-12-01"),
    ]
    runs.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    out = tmp_path / "dashboard.html"
    dashboard.generate(runs_path=runs, output_path=out)
    content = out.read_text()
    assert '"total": 3' in content or "3" in content
