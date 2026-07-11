"""
Database layer - stores every PA request + agent outputs + final decision +
human reviewer action, for the audit trail.

Uses SQLite for simplicity (freelancer/showcase scope). Swap to Postgres
for production by changing DATABASE_URL.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "prior_auth.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pa_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL,
            patient_age INTEGER,
            diagnosis TEXT,
            requested_treatment TEXT,
            ai_recommendation TEXT,
            weighted_confidence_score REAL,
            full_result_json TEXT,
            reviewer_decision TEXT DEFAULT NULL,
            reviewer_notes TEXT DEFAULT NULL,
            created_at TEXT,
            reviewed_at TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_pa_request(case: dict, pipeline_result: dict) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO pa_requests
        (case_id, patient_age, diagnosis, requested_treatment,
         ai_recommendation, weighted_confidence_score, full_result_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case["case_id"],
            case.get("patient_age"),
            case.get("diagnosis"),
            case.get("requested_treatment"),
            pipeline_result["recommendation"],
            pipeline_result["weighted_confidence_score"],
            json.dumps(pipeline_result),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def update_reviewer_decision(record_id: int, decision: str, notes: str = ""):
    """decision should be 'ACCEPT' or 'OVERRIDE'"""
    conn = get_connection()
    conn.execute(
        """
        UPDATE pa_requests
        SET reviewer_decision = ?, reviewer_notes = ?, reviewed_at = ?
        WHERE id = ?
        """,
        (decision, notes, datetime.utcnow().isoformat(), record_id),
    )
    conn.commit()
    conn.close()


def get_all_requests() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM pa_requests ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_request_by_id(record_id: int) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM pa_requests WHERE id = ?", (record_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
