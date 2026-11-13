import csv, json
from solution.db import connect
from solution.lead_ingest import ingest_lead_file
from solution.security import PIIProtector

def test_required_validation_and_duplicate_merge(tmp_path):
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    schema = {
        "workflow_id": "sample",
        "fields": [
            {"name": "customer_name", "type": "string", "required": True, "pii": True, "aliases": ["Name"]},
            {"name": "phone", "type": "phone", "required": True, "pii": True, "aliases": ["Mobile"]},
            {"name": "ref", "type": "string", "required": True, "reference": True, "aliases": ["Ref"]},
            {"name": "language", "type": "enum", "required": False, "values": ["en", "te"], "aliases": ["Language"]},
        ],
    }
    (schema_dir / "sample.json").write_text(json.dumps(schema))
    csv_path = tmp_path / "batch_001.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Mobile", "Ref", "Language"])
        writer.writerow(["Alice", "+91 98765 43210", "R1", "EN"])
        writer.writerow(["", "9876543211", "R2", "en"])
        writer.writerow(["Alice Updated", "9876543210", "R3", "te"])
    conn = connect(tmp_path / "db.sqlite")
    protector = PIIProtector(key=b"MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    result = ingest_lead_file(conn, csv_path, "sample", "batch_001", schema_dir, protector)
    conn.commit()
    assert result == {"rows_total": 3, "rows_rejected": 1, "duplicates": 1, "warnings": 0}
    leads = conn.execute("SELECT * FROM leads").fetchall()
    assert len(leads) == 1
    assert leads[0]["batch_id"] == "batch_001"
    assert protector.decrypt(leads[0]["customer_name_ciphertext"]) == "Alice Updated"
    rejection = conn.execute("SELECT reason FROM lead_rejections").fetchone()
    assert rejection["reason"] == "missing_required:customer_name"
    conn.close()
