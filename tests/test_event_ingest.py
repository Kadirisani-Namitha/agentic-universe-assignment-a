import json
from solution.db import connect
from solution.event_ingest import ingest_event_file
from solution.security import PIIProtector


def test_malformed_and_duplicate_event_lines(tmp_path):
    path = tmp_path / "events.jsonl"
    event = {
        "event_id": "evt-1", "event_type": "call.initiated",
        "workflow_id": "motor_renewal", "call_id": "call-1",
        "occurred_at": "2026-10-03T10:00:00+05:30",
        "phone": "9876543210", "payload": {},
    }
    path.write_text(
        "not json\n" + json.dumps({"event_type": "call.connected"}) + "\n"
        + json.dumps(event) + "\n" + json.dumps(event) + "\n\n",
        encoding="utf-8",
    )
    conn = connect(tmp_path / "events.sqlite")
    protector = PIIProtector(key=b"MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    result = ingest_event_file(conn, path, "drop-1", protector)
    conn.commit()
    assert result == {
        "events_total": 4,
        "malformed_events": 2,
        "duplicate_events_dropped": 1,
    }
    assert conn.execute("SELECT COUNT(*) FROM interaction_events").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM event_quarantine").fetchone()[0] == 2
    conn.close()
