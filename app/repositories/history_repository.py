from app.db import connect, ensure_history_table
from app.core.constants import DB_PATH


def insert_daily_history(date_str: str, used_tb: float):
    conn = connect(DB_PATH)
    try:
        ensure_history_table(conn)
        exists = conn.execute(
            "SELECT 1 FROM storage_history WHERE date=?",
            (date_str,),
        ).fetchone()

        if not exists:
            conn.execute(
                "INSERT INTO storage_history(date, used_tb) VALUES(?, ?)",
                (date_str, used_tb),
            )
            conn.commit()
    finally:
        conn.close()


def get_history_rows():
    conn = connect(DB_PATH)
    try:
        ensure_history_table(conn)
        rows = conn.execute(
            "SELECT date, used_tb FROM storage_history ORDER BY date"
        ).fetchall()
        return rows
    finally:
        conn.close()    