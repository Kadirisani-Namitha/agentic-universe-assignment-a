from __future__ import annotations
import hashlib
from pathlib import Path
from .db import connect
from .lead_ingest import ingest_lead_file
from .event_ingest import ingest_event_file
from .security import PIIProtector
def _hash(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()
def _bump(conn,key,value):
 conn.execute("INSERT INTO data_quality_counters(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=value+excluded.value",(key,value))
def ingest_drop(drop_dir:Path,db_path:Path|None=None,schema_dir:Path|None=None):
 drop_dir=Path(drop_dir); schema_dir=schema_dir or Path(__file__).resolve().parents[1]/"assignment-a-data"/"schemas"; drop_key=drop_dir.resolve().as_posix(); protector=PIIProtector(); conn=connect(db_path); totals={}
 try:
  conn.execute("BEGIN")
  if conn.execute("SELECT 1 FROM ingestion_drops WHERE drop_key=?",(drop_key,)).fetchone():conn.rollback();return {"already_ingested":1}
  lead_root=drop_dir/"leads"
  if lead_root.exists():
   for wfdir in sorted(p for p in lead_root.iterdir() if p.is_dir()):
    for path in sorted(wfdir.glob("*.csv"),key=lambda p:p.name):
     file_key=f"{drop_key}:{path.relative_to(drop_dir).as_posix()}"; digest=_hash(path); old=conn.execute("SELECT file_sha256 FROM ingestion_files WHERE file_key=?",(file_key,)).fetchone()
     if old:
      if old["file_sha256"]!=digest:raise RuntimeError(f"File changed after ingest: {path}")
      continue
     r=ingest_lead_file(conn,path,wfdir.name,path.stem,schema_dir,protector)
     for src,dst in (("rows_total","lead_rows_total"),("rows_rejected","lead_rows_rejected"),("duplicates","duplicate_lead_rows_merged"),("warnings","field_warnings")):totals[dst]=totals.get(dst,0)+r[src]
     conn.execute("INSERT INTO ingestion_files(file_key,drop_key,file_sha256) VALUES(?,?,?)",(file_key,drop_key,digest))
  event_root=drop_dir/"events"
  if event_root.exists():
   for path in sorted(event_root.glob("*.jsonl"),key=lambda p:p.name):
    file_key=f"{drop_key}:{path.relative_to(drop_dir).as_posix()}"; digest=_hash(path); old=conn.execute("SELECT file_sha256 FROM ingestion_files WHERE file_key=?",(file_key,)).fetchone()
    if old:
     if old["file_sha256"]!=digest:raise RuntimeError(f"File changed after ingest: {path}")
     continue
    r=ingest_event_file(conn,path,drop_key,protector)
    for k,v in r.items():totals[k]=totals.get(k,0)+v
    conn.execute("INSERT INTO ingestion_files(file_key,drop_key,file_sha256) VALUES(?,?,?)",(file_key,drop_key,digest))
  conn.execute("INSERT INTO ingestion_drops(drop_key) VALUES(?)",(drop_key,))
  for k,v in totals.items():_bump(conn,k,v)
  conn.commit();return totals
 except Exception:conn.rollback();raise
 finally:conn.close()
