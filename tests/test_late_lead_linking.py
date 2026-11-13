import csv, json
from pathlib import Path

from solution.pipeline import ingest_drop
from solution.reporting import generate_reports


def test_events_arriving_before_lead_are_linked_after_later_drop(tmp_path, monkeypatch):
    monkeypatch.setenv("AU_PII_KEY", "stable-test-secret-for-late-linking")
    schema_dir = Path(__file__).resolve().parents[1] / "assignment-a-data" / "schemas"
    drop1 = tmp_path / "drop_1"
    (drop1 / "events").mkdir(parents=True)
    events = [
        {"event_id": "late-1", "event_type": "call.initiated", "workflow_id": "motor_renewal", "call_id": "late-call", "occurred_at": "2026-10-03T10:00:00+05:30", "phone": "9876543210", "payload": {}},
        {"event_id": "late-2", "event_type": "call.connected", "workflow_id": "motor_renewal", "call_id": "late-call", "occurred_at": "2026-10-03T10:00:10+05:30", "phone": "9876543210", "payload": {}},
        {"event_id": "late-3", "event_type": "disposition.set", "workflow_id": "motor_renewal", "call_id": "late-call", "occurred_at": "2026-10-03T10:01:00+05:30", "phone": "9876543210", "payload": {"disposition_code": "renewed"}},
    ]
    (drop1 / "events" / "events_0001.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    drop2 = tmp_path / "drop_2"
    lead_dir = drop2 / "leads" / "motor_renewal"
    lead_dir.mkdir(parents=True)
    with (lead_dir / "batch_003.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["customer_name", "phone", "policy_number"])
        writer.writerow(["Late Arrival", "9876543210", "POL-LATE"])

    db_path = tmp_path / "late.sqlite"
    first = ingest_drop(drop1, db_path=db_path, schema_dir=schema_dir)
    assert first["events_total"] == 3
    before = generate_reports(tmp_path / "before", db_path=db_path, schema_dir=schema_dir)
    assert before["orphan_events"] == 3

    ingest_drop(drop2, db_path=db_path, schema_dir=schema_dir)
    after = generate_reports(tmp_path / "after", db_path=db_path, schema_dir=schema_dir)
    assert after["orphan_events"] == 0
    import csv as csv_module
    with (tmp_path / "after" / "lead_report.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv_module.DictReader(f))
    assert rows[0]["total_calls"] == "1"
    assert rows[0]["current_disposition"] == "renewed"
