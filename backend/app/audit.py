from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Optional


DB_PATH = os.getenv("AUDIT_DB_PATH", "/data/audit.db")

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts INTEGER NOT NULL,
              app_key TEXT,
              action TEXT,
              result TEXT,
              actor TEXT,
              client_ip TEXT,
              error TEXT
            )
            """
        )
        _conn.commit()
    return _conn


def init_db():
    # Ensure the DB file + schema exist early (useful for verification).
    with _lock:
        _connect()


def log_action(
    *,
    app_key: str,
    action: str,
    result: str,
    actor: str,
    client_ip: str,
    error: str | None,
):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO audit (ts, app_key, action, result, actor, client_ip, error) VALUES (?,?,?,?,?,?,?)",
            (int(time.time()), app_key, action, result, actor, client_ip, (error or "")[:500]),
        )
        conn.commit()
