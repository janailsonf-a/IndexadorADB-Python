import time
from pathlib import Path

from fastapi import HTTPException

from app.db import connect, get_meta
from app.core.constants import DB_PATH, ROOT_DIR
from app.repositories.db_connection import db_connect


def assert_db_root_dir():
    conn = connect(DB_PATH)
    try:
        db_root = get_meta(conn, "root_dir")
    finally:
        conn.close()

    if not db_root:
        raise HTTPException(500, "Banco não inicializado. Rode: python -m app.indexer")

    if Path(db_root).resolve() != ROOT_DIR:
        raise HTTPException(500, "ROOT_DIR diferente do indexado. Ajuste o .env e reindexe.")


def db_count_files() -> int:
    conn = db_connect()
    try:
        row = conn.execute("SELECT count(1) c FROM files_meta").fetchone()
        return int(row["c"]) if row else 0
    finally:
        conn.close()


def get_indexer_status_data():
    conn = db_connect()
    try:
        row = conn.execute(
            """
            SELECT processed, total, start_time, last_finished_time, last_duration_sec,
                   last_new, last_updated, last_deleted, last_error
            FROM indexer_status WHERE id = 1
            """
        ).fetchone()
    finally:
        conn.close()

    if not row or not row["start_time"]:
        return {
            "processed": 0,
            "total": 0,
            "percent": 0,
            "speed": 0,
            "eta_sec": 0,
            "last_error": None,
        }

    processed = int(row["processed"] or 0)
    total = int(row["total"] or 0)
    start = float(row["start_time"] or time.time())
    elapsed = max(1.0, time.time() - start)
    speed = round(processed / elapsed, 1)
    percent = round((processed / total) * 100, 1) if total else 0
    eta = round((total - processed) / speed, 1) if speed > 0 and total > processed else 0

    return {
        "processed": processed,
        "total": total,
        "percent": percent,
        "speed": speed,
        "eta_sec": eta,
        "last_finished_time": row["last_finished_time"],
        "last_duration_sec": row["last_duration_sec"],
        "last_new": row["last_new"],
        "last_updated": row["last_updated"],
        "last_deleted": row["last_deleted"],
        "last_error": row["last_error"],
    }