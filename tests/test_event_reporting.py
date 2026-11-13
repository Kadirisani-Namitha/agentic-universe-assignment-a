import json
from pathlib import Path

from solution.db import connect
from solution.normalization import parse_timestamp, iso_ist, normalize_phone
from solution.reporting import generate_reports
from solution.security import PIIProtector


def _event(conn, protector, event_id, kind, call_id, phone, when, payload=None):
    phone_hash = protector.phone_hash(normalize_phone(phone)) if phone else None
    conn.execute(
        """INSERT INTO interaction_events
        (event_id,event_type,workflow_id,call_id,occurred_at,occurred_at_ist,
         phone_hash,payload_json,raw_fingerprint,first_seen_drop)
        VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (event_id, kind, "motor_renewal", call_id, when,
         iso_ist(parse_timestamp(when)), phone_hash,
         json.dumps(payload or {}), event_id, "drop-test"),
    )


def test_override_success_and_orphan_linking(tmp_path, monkeypatch):
    monkeypatch.setenv("AU_PII_KEY", "stable-test-secret-for-reporting")
    db_path = tmp_path / "ledger.sqlite"
    conn = connect(db_path)
    protector = PIIProtector()
    phone = "+919876543210"
    conn.execute(
        """INSERT INTO leads
        (workflow_id,phone_hash,phone_ciphertext,customer_name_ciphertext,
         external_ref,batch_id,fields_json)
        VALUES(?,?,?,?,?,?,?)""",
        ("motor_renewal", protector.phone_hash(phone), protector.encrypt(phone),
         protector.encrypt("Test Customer"), "POL-1", "batch_001", "{}"),
    )
    _event(conn, protector, "e1", "call.initiated", "call-1", phone, "2026-10-03 10:00:00")
    _event(conn, protector, "e2", "call.connected", "call-1", phone, "2026-10-03 10:00:10")
    _event(conn, protector, "e3", "disposition.set", "call-1", phone,
           "2026-10-03 10:01:00", {"disposition_code": "not_interested"})
    # Unknown code must be counted and ignored.
    _event(conn, protector, "e4", "disposition.set", "call-1", phone,
           "2026-10-03 10:02:00", {"disposition_code": "not_a_real_code"})
    # Override has no phone, but links through call_id.
    _event(conn, protector, "e5", "disposition.override", "call-1", None,
           "2026-10-03 10:03:00", {"disposition_code": "renewed"})
    _event(conn, protector, "e6", "call.initiated", "orphan-call", "+919999999999",
           "2026-10-03 10:04:00")
    conn.commit()
    conn.close()

    out = tmp_path / "reports"
    quality = generate_reports(out, db_path=db_path)
    assert quality["orphan_events"] == 1
    assert quality["unknown_disposition_events"] == 1

    import csv
    with (out / "lead_report.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["bucket"] == "completed"
    assert rows[0]["current_disposition"] == "renewed"
    assert rows[0]["ever_success"] == "true"

    with (out / "daily_overview.csv").open(newline="", encoding="utf-8") as f:
        daily = list(csv.DictReader(f))
    assert daily[0]["total_calls"] == "1"
    assert daily[0]["connected_calls"] == "1"
    assert daily[0]["success_leads"] == "1"
