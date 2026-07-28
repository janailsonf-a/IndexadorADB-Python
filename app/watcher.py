from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from pathlib import Path

from watchfiles import watch

from app.config import settings
from app.db import connect, ensure_files_schema, ensure_metadata_columns, ensure_content_hash_column
from app.indexer import _should_ignore, _ext
from app.utils import path_hash, content_hash_of_file

settings.validate()

ROOT_DIR = Path(settings.root_dir).expanduser().resolve()
DB_PATH = settings.db_path
DEBOUNCE_SECONDS = 1
last_event_time: dict[str, float] = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("indexador.watcher")


def db_connect():
    conn = connect(DB_PATH)
    ensure_files_schema(conn)
    ensure_metadata_columns(conn)
    ensure_content_hash_column(conn)
    return conn


def fmt_dt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def should_process(rel_path: str) -> bool:
    return not _should_ignore(rel_path)


def index_file(full_path: str, rel_path: str):
    path = Path(full_path)
    if not path.exists() or path.is_dir() or not should_process(rel_path):
        return

    try:
        stat = path.stat()
        conn = db_connect()
        conn.execute(
            """
            INSERT INTO files_meta (
                filename, rel_path, ext, size_bytes, created_at, modified_at,
                path_hash, mtime_ns, last_seen_run, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rel_path) DO UPDATE SET
                filename=excluded.filename,
                ext=excluded.ext,
                size_bytes=excluded.size_bytes,
                created_at=excluded.created_at,
                modified_at=excluded.modified_at,
                path_hash=excluded.path_hash,
                mtime_ns=excluded.mtime_ns,
                last_seen_run=excluded.last_seen_run,
                content_hash=excluded.content_hash
            """,
            (
                path.name,
                rel_path,
                _ext(path.name),
                stat.st_size,
                fmt_dt(stat.st_ctime),
                fmt_dt(stat.st_mtime),
                path_hash(rel_path),
                getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)),
                int(time.time()),
                content_hash_of_file(full_path),
            ),
        )
        conn.commit()
        conn.close()
        logger.info("Indexado: %s", rel_path)
    except Exception:
        logger.exception("Erro ao indexar %s", rel_path)


def remove_file(rel_path: str):
    try:
        conn = db_connect()
        conn.execute("DELETE FROM files_meta WHERE rel_path=?", (rel_path,))
        conn.commit()
        conn.close()
        logger.info("Removido: %s", rel_path)
    except Exception:
        logger.exception("Erro ao remover %s", rel_path)


def safe_index(full_path: str, rel_path: str):
    now = time.time()
    if rel_path in last_event_time and now - last_event_time[rel_path] < DEBOUNCE_SECONDS:
        return
    last_event_time[rel_path] = now
    index_file(full_path, rel_path)


def start_watcher():
    logger.info("Watcher ativo em %s", ROOT_DIR)
    for changes in watch(str(ROOT_DIR), recursive=True):
        for change, changed_path in changes:
            try:
                rel_path = os.path.relpath(changed_path, ROOT_DIR)
                if rel_path.startswith(".."):
                    continue
                if str(change).endswith("deleted"):
                    remove_file(rel_path)
                else:
                    safe_index(changed_path, rel_path)
            except Exception:
                logger.exception("Erro ao processar evento do watcher")


if __name__ == "__main__":
    start_watcher()
