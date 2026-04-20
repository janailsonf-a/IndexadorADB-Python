import sqlite3

from app.repositories.db_connection import db_connect


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def ensure_activities_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_email TEXT,
            user_name TEXT,
            action TEXT NOT NULL,
            filename TEXT,
            rel_path TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    if not _column_exists(conn, "activities", "user_id"):
        conn.execute("ALTER TABLE activities ADD COLUMN user_id INTEGER")

    if not _column_exists(conn, "activities", "user_email"):
        conn.execute("ALTER TABLE activities ADD COLUMN user_email TEXT")

    if not _column_exists(conn, "activities", "user_name"):
        conn.execute("ALTER TABLE activities ADD COLUMN user_name TEXT")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_created_at ON activities(created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_action ON activities(action)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_user_id ON activities(user_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_user_email ON activities(user_email)"
    )
    conn.commit()


def insert_activity(
    *,
    user_id: int | None,
    user_email: str | None,
    user_name: str | None,
    action: str,
    filename: str | None,
    rel_path: str | None,
    created_at: str,
):
    conn = db_connect()
    try:
        conn.execute(
            """
            INSERT INTO activities (
                user_id,
                user_email,
                user_name,
                action,
                filename,
                rel_path,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, user_email, user_name, action, filename, rel_path, created_at),
        )
        conn.commit()
    finally:
        conn.close()


def list_activities(limit: int):
    conn = db_connect()
    try:
        rows = conn.execute(
            """
            SELECT
                user_id,
                user_email,
                user_name,
                action,
                filename,
                rel_path,
                created_at
            FROM activities
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows
    finally:
        conn.close()


def list_activities_for_user(user_id: int, limit: int):
    conn = db_connect()
    try:
        rows = conn.execute(
            """
            SELECT
                user_id,
                user_email,
                user_name,
                action,
                filename,
                rel_path,
                created_at
            FROM activities
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
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