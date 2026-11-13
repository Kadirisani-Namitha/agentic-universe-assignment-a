from __future__ import annotations
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("AU_DB_PATH", ROOT / "agentic_universe.sqlite3"))

def get_pii_key() -> bytes:
    import base64, hashlib
    from cryptography.fernet import Fernet
    secret = os.environ.get("AU_PII_KEY")
    if not secret:
        raise RuntimeError("AU_PII_KEY is required; set a stable high-entropy secret")
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
