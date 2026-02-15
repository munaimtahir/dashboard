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
            CREATE TABLE IF NOT EXISTS actions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              timestamp INTEGER NOT NULL,
              app_key TEXT NOT NULL,
              action TEXT NOT NULL,
              result TEXT NOT NULL,
              exit_code INTEGER,
              message TEXT,
              client_ip TEXT
            );
            """
        )
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_actions_ts ON actions(timestamp);")
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_actions_app ON actions(app_key);")
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
    client_ip: str,
    result: str,
    exit_code: int | None,
    message: str | None,
):
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO actions (timestamp, app_key, action, result, exit_code, message, client_ip) VALUES (?,?,?,?,?,?,?)",
            (
                int(time.time()),
                (app_key or "")[:100],
                (action or "")[:20],
                (result or "")[:20],
                exit_code,
                (message or "")[:2000],
                (client_ip or "")[:100],
            ),
        )
def list_recent_actions(limit: int = 50) -> list[dict]:
    with _lock:
        conn = _connect()
        cursor = conn.execute(
            "SELECT id, timestamp, app_key, action, result, exit_code, message, client_ip FROM actions ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "app_key": r[2],
                "action": r[3],
                "result": r[4],
                "exit_code": r[5],
                "message": r[6],
                "client_ip": r[7],
            }
            for r in rows
        ]
