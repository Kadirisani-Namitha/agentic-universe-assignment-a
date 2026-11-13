from __future__ import annotations
import sqlite3
from pathlib import Path
from .config import DB_PATH
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS leads (
 id INTEGER PRIMARY KEY AUTOINCREMENT, workflow_id TEXT NOT NULL, phone_hash TEXT NOT NULL,
 phone_ciphertext BLOB NOT NULL, customer_name_ciphertext BLOB NOT NULL,
 external_ref TEXT NOT NULL, batch_id TEXT NOT NULL, fields_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(workflow_id,phone_hash));
CREATE TABLE IF NOT EXISTS lead_rejections (
 id INTEGER PRIMARY KEY AUTOINCREMENT, workflow_id TEXT NOT NULL, batch_id TEXT NOT NULL,
 row_number INTEGER NOT NULL, reason TEXT NOT NULL, UNIQUE(workflow_id,batch_id,row_number));
CREATE TABLE IF NOT EXISTS ingestion_drops (drop_key TEXT PRIMARY KEY, ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ingestion_files (file_key TEXT PRIMARY KEY, drop_key TEXT NOT NULL,
 file_sha256 TEXT NOT NULL, ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS interaction_events (
 event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, workflow_id TEXT NOT NULL, call_id TEXT,
 occurred_at TEXT, occurred_at_ist TEXT, phone_hash TEXT, payload_json TEXT NOT NULL,
 raw_fingerprint TEXT NOT NULL, first_seen_drop TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_events_call ON interaction_events(workflow_id,call_id);
CREATE INDEX IF NOT EXISTS idx_events_phone ON interaction_events(workflow_id,phone_hash);
CREATE INDEX IF NOT EXISTS idx_events_time ON interaction_events(workflow_id,event_type,occurred_at_ist);
CREATE TABLE IF NOT EXISTS event_quarantine (
 id INTEGER PRIMARY KEY AUTOINCREMENT, drop_key TEXT NOT NULL, file_name TEXT NOT NULL,
 line_number INTEGER NOT NULL, reason TEXT NOT NULL, raw_fingerprint TEXT NOT NULL,
 UNIQUE(drop_key,file_name,line_number));
CREATE TABLE IF NOT EXISTS data_quality_counters (key TEXT PRIMARY KEY,value INTEGER NOT NULL);
"""
def connect(path: Path|str|None=None):
 p=Path(path) if path else DB_PATH; p.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(p); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA journal_mode=WAL"); c.executescript(SCHEMA); return c
