"""Persistence for issued forecasts, pipeline runs and the inference audit log.

SQLite (stdlib) by default so the prototype runs anywhere. The schema is
portable to PostgreSQL/PostGIS (see docs/architecture.md) by switching
``TROPICAST_DB_URL`` in a later release; v1 ships SQLite only.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from tropicast import config

_LOCK = threading.Lock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS forecasts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sid TEXT NOT NULL, issue_time TEXT NOT NULL, processed_at TEXT NOT NULL,
  track_model TEXT, intensity_model TEXT, data_version TEXT, source TEXT,
  payload TEXT NOT NULL,
  UNIQUE (sid, issue_time, track_model)
);
CREATE INDEX IF NOT EXISTS ix_fc_sid ON forecasts(sid, issue_time);
CREATE TABLE IF NOT EXISTS pipeline_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT, finished_at TEXT, duration_s REAL, status TEXT, details TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL, kind TEXT NOT NULL, sid TEXT, message TEXT NOT NULL, dedup_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL, endpoint TEXT, sid TEXT, issue_time TEXT,
  model_version TEXT, data_version TEXT, duration_ms REAL, status TEXT, error TEXT
);
"""


def db_path() -> Path:
    p = Path(os.environ.get("TROPICAST_DB", config.DATA_DIR / "tropicast.sqlite"))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@contextmanager
def connect():
    with _LOCK:
        con = sqlite3.connect(db_path())
        con.row_factory = sqlite3.Row
        try:
            con.executescript(SCHEMA)
            yield con
            con.commit()
        finally:
            con.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_forecast(fc: dict, source: str) -> None:
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO forecasts (sid, issue_time, processed_at, track_model, intensity_model,"
            " data_version, source, payload) VALUES (?,?,?,?,?,?,?,?)",
            (fc["sid"], fc["issue_time"], fc["processed_at"], fc["model"]["track"], fc["model"]["intensity"],
             fc["model"]["data_version"], source, json.dumps(fc)))


def latest_forecasts(limit: int = 50) -> list[dict]:
    with connect() as con:
        rows = con.execute(
            "SELECT payload FROM forecasts f WHERE issue_time = (SELECT MAX(issue_time) FROM forecasts g"
            " WHERE g.sid = f.sid) ORDER BY issue_time DESC LIMIT ?", (limit,)).fetchall()
    return [json.loads(r["payload"]) for r in rows]


def forecast_history(sid: str) -> list[dict]:
    with connect() as con:
        rows = con.execute("SELECT payload FROM forecasts WHERE sid=? ORDER BY issue_time", (sid,)).fetchall()
    return [json.loads(r["payload"]) for r in rows]


def record_run(started: str, duration_s: float, status: str, details: dict) -> None:
    with connect() as con:
        con.execute("INSERT INTO pipeline_runs (started_at, finished_at, duration_s, status, details)"
                    " VALUES (?,?,?,?,?)", (started, now(), duration_s, status, json.dumps(details, default=str)))


def recent_runs(limit: int = 20) -> list[dict]:
    with connect() as con:
        rows = con.execute("SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{**dict(r), "details": json.loads(r["details"] or "{}")} for r in rows]


def audit(endpoint: str, sid: str | None, issue_time: str | None, model_version: str | None,
          data_version: str | None, duration_ms: float, status: str, error: str | None = None) -> None:
    with connect() as con:
        con.execute("INSERT INTO audit_log (at, endpoint, sid, issue_time, model_version, data_version,"
                    " duration_ms, status, error) VALUES (?,?,?,?,?,?,?,?,?)",
                    (now(), endpoint, sid, issue_time, model_version, data_version, duration_ms, status, error))


def audit_tail(limit: int = 100) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]


def notify(kind: str, message: str, sid: str | None = None, dedup_key: str | None = None) -> bool:
    """Insert a notification; returns False if ``dedup_key`` was already notified."""
    with connect() as con:
        try:
            con.execute("INSERT INTO notifications (at, kind, sid, message, dedup_key) VALUES (?,?,?,?,?)",
                        (now(), kind, sid, message, dedup_key))
            return True
        except sqlite3.IntegrityError:
            return False


def notifications(limit: int = 50) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,))]
