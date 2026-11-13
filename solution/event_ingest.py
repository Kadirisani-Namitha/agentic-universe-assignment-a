from __future__ import annotations
import hashlib,json
from pathlib import Path
from .normalization import ValidationError,normalize_phone,parse_timestamp,iso_ist
def ingest_event_file(conn,path:Path,drop_key:str,protector):
 counts={"events_total":0,"malformed_events":0,"duplicate_events_dropped":0}
 with path.open("r",encoding="utf-8") as f:
  for line_no,line in enumerate(f,1):
   if not line.strip():continue
   counts["events_total"]+=1; fingerprint=hashlib.sha256(line.encode()).hexdigest()
   try:
    event=json.loads(line)
    if not isinstance(event,dict) or not event.get("event_id"):raise ValueError()
   except (json.JSONDecodeError,ValueError,TypeError):
    counts["malformed_events"]+=1
    conn.execute("INSERT OR IGNORE INTO event_quarantine(drop_key,file_name,line_number,reason,raw_fingerprint) VALUES(?,?,?,?,?)",(drop_key,path.name,line_no,"malformed_or_missing_event_id",fingerprint));continue
   event_id=str(event["event_id"])
   if conn.execute("SELECT 1 FROM interaction_events WHERE event_id=?",(event_id,)).fetchone():counts["duplicate_events_dropped"]+=1;continue
   wf=str(event.get("workflow_id") or ""); et=str(event.get("event_type") or ""); raw_ts=event.get("occurred_at"); ts_ist=None
   if raw_ts:
    try:ts_ist=iso_ist(parse_timestamp(raw_ts))
    except ValidationError:pass
   phash=None
   if event.get("phone"):
    try:phash=protector.phone_hash(normalize_phone(event["phone"]))
    except ValidationError:pass
   payload=event.get("payload") if isinstance(event.get("payload"),dict) else {}
   conn.execute("INSERT INTO interaction_events(event_id,event_type,workflow_id,call_id,occurred_at,occurred_at_ist,phone_hash,payload_json,raw_fingerprint,first_seen_drop) VALUES(?,?,?,?,?,?,?,?,?,?)",(event_id,et,wf,event.get("call_id"),str(raw_ts or ""),ts_ist,phash,json.dumps(payload,sort_keys=True),fingerprint,drop_key))
 return counts
