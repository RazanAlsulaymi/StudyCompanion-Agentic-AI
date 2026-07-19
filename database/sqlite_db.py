import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from models.schemas import Task

DB_PATH = Path(__file__).resolve().parent.parent / "study_companion.db"


def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def db_init():
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        created_at TEXT,
        last_seen_at TEXT,
        prefs_json TEXT,
        study_style_json TEXT,
        last_score INTEGER DEFAULT 0,
        last_total INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        ts TEXT,
        event_type TEXT,
        payload_json TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS task_status (
        session_id TEXT,
        task_id TEXT,
        title TEXT,
        kind TEXT,
        est_min INTEGER,
        status TEXT,
        updated_at TEXT,
        PRIMARY KEY (session_id, task_id)
    )
    """)

    conn.commit()
    conn.close()


def db_log_event(session_id: str, event_type: str, payload: Dict):
    conn = db_connect()
    conn.execute(
        "INSERT INTO events(session_id, ts, event_type, payload_json) VALUES (?,?,?,?)",
        (
            session_id,
            datetime.utcnow().isoformat(),
            event_type,
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def db_upsert_session(session_id: str, prefs: Dict, study_style: Dict):
    now = datetime.utcnow().isoformat()

    conn = db_connect()

    conn.execute(
        """
        INSERT INTO sessions(session_id, created_at, last_seen_at, prefs_json, study_style_json)
        VALUES (?,?,?,?,?)
        ON CONFLICT(session_id) DO UPDATE SET
          last_seen_at=excluded.last_seen_at,
          prefs_json=excluded.prefs_json,
          study_style_json=excluded.study_style_json
        """,
        (
            session_id,
            now,
            now,
            json.dumps(prefs, ensure_ascii=False),
            json.dumps(study_style, ensure_ascii=False),
        ),
    )

    conn.commit()
    conn.close()


def db_save_score(session_id: str, score: int, total: int):
    now = datetime.utcnow().isoformat()

    conn = db_connect()

    conn.execute(
        """
        UPDATE sessions
        SET last_seen_at=?, last_score=?, last_total=?
        WHERE session_id=?
        """,
        (
            now,
            score,
            total,
            session_id,
        ),
    )

    conn.commit()
    conn.close()


def db_store_tasks(session_id: str, tasks: List[Task]):
    now = datetime.utcnow().isoformat()

    conn = db_connect()
    cur = conn.cursor()

    for t in tasks:
        cur.execute(
            """
            INSERT INTO task_status(
                session_id,
                task_id,
                title,
                kind,
                est_min,
                status,
                updated_at
            )
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(session_id, task_id)
            DO UPDATE SET
                title=excluded.title,
                kind=excluded.kind,
                est_min=excluded.est_min,
                status=excluded.status,
                updated_at=excluded.updated_at
            """,
            (
                session_id,
                t.id,
                t.title,
                t.kind,
                t.est_min,
                "pending",
                now,
            ),
        )

    conn.commit()
    conn.close()


def db_mark_task_done(session_id: str, task_id: str):
    now = datetime.utcnow().isoformat()

    conn = db_connect()

    conn.execute(
        """
        UPDATE task_status
        SET status='done',
            updated_at=?
        WHERE session_id=?
          AND task_id=?
        """,
        (
            now,
            session_id,
            task_id,
        ),
    )

    conn.commit()
    conn.close()