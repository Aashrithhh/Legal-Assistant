# case_history.py
import os
import json
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "case_history.db")


def init_case_history_db() -> None:
    """
    Create the SQLite database + table if they don't exist yet.
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                filenames_json TEXT NOT NULL,
                analysis TEXT NOT NULL,
                issues_json TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_case(
    metadata: Dict[str, str],
    filenames: List[str],
    analysis: str,
    issues: List[Dict[str, Any]],
) -> int:
    """
    Insert a new case row and return the new case ID.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO cases (
                created_at, metadata_json, filenames_json, analysis, issues_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat(timespec="seconds") + "Z",
                json.dumps(metadata, ensure_ascii=False),
                json.dumps(filenames, ensure_ascii=False),
                analysis,
                json.dumps(issues, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_cases(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Return a list of recent cases, newest first.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, created_at, metadata_json, filenames_json
            FROM cases
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    cases: List[Dict[str, Any]] = []
    for row in rows:
        case_id, created_at, meta_json, files_json = row
        try:
            metadata = json.loads(meta_json)
        except Exception:
            metadata = {}
        try:
            filenames = json.loads(files_json)
        except Exception:
            filenames = []

        cases.append(
            {
                "id": case_id,
                "created_at": created_at,
                "metadata": metadata,
                "filenames": filenames,
            }
        )
    return cases


def get_case(case_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a single case by ID, or None if not found.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, created_at, metadata_json, filenames_json, analysis, issues_json
            FROM cases
            WHERE id = ?
            """,
            (case_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    cid, created_at, meta_json, files_json, analysis, issues_json = row
    try:
        metadata = json.loads(meta_json)
    except Exception:
        metadata = {}
    try:
        filenames = json.loads(files_json)
    except Exception:
        filenames = []
    try:
        issues = json.loads(issues_json)
    except Exception:
        issues = []

    return {
        "id": cid,
        "created_at": created_at,
        "metadata": metadata,
        "filenames": filenames,
        "analysis": analysis,
        "issues": issues,
    }
