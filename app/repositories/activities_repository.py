import sqlite3

from app.repositories.db_connection import db_connect


def ensure_activities_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            filename TEXT,
            rel_path TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_created_at ON activities(created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_action ON activities(action)"
    )


def insert_activity(action: str, filename: str | None, rel_path: str | None, created_at: str):
    conn = db_connect()
    try:
        conn.execute(
            "INSERT INTO activities (action, filename, rel_path, created_at) VALUES (?, ?, ?, ?)",
            (action, filename, rel_path, created_at),
        )
        conn.commit()
    finally:
        conn.close()


def list_activities(limit: int):
    conn = db_connect()
    try:
        rows = conn.execute(
            "SELECT action, filename, rel_path, created_at FROM activities ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return rows
    finally:
        conn.close()


def clear_all_activities():
    conn = db_connect()
    try:
        conn.execute("DELETE FROM activities")
        conn.commit()
    finally:
        conn.close()