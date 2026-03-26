import os
import sqlite3
from typing import Optional


def connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row

    # WAL ajuda em leitura concorrente (API + indexer)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA busy_timeout=10000;")
    return conn


def ensure_files_schema(conn: sqlite3.Connection) -> None:
    """
    Tabelas:
      - meta: chave/valor
      - files_meta: metadados reais (fonte da verdade)
      - files: FTS5 (busca por filename/rel_path) sincronizado via triggers
    """
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS files_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            rel_path TEXT NOT NULL UNIQUE,
            ext TEXT,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            modified_at TEXT,
            path_hash TEXT,
            mtime_ns INTEGER NOT NULL DEFAULT 0,
            last_seen_run INTEGER NOT NULL DEFAULT 0
        );
    """)

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_files_meta_rel_path ON files_meta(rel_path);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_files_meta_filename ON files_meta(filename);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_files_meta_last_seen ON files_meta(last_seen_run);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_files_meta_mtime_ns ON files_meta(mtime_ns);"
    )

    # FTS5 sincronizado com content=files_meta
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS files
        USING fts5(
            filename,
            rel_path,
            content='files_meta',
            content_rowid='id'
        );
    """)

    # Triggers para manter o FTS sincronizado
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS files_meta_ai AFTER INSERT ON files_meta BEGIN
          INSERT INTO files(rowid, filename, rel_path) VALUES (new.id, new.filename, new.rel_path);
        END;
    """)
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS files_meta_ad AFTER DELETE ON files_meta BEGIN
          INSERT INTO files(files, rowid, filename, rel_path) VALUES('delete', old.id, old.filename, old.rel_path);
        END;
    """)
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS files_meta_au AFTER UPDATE ON files_meta BEGIN
          INSERT INTO files(files, rowid, filename, rel_path) VALUES('delete', old.id, old.filename, old.rel_path);
          INSERT INTO files(rowid, filename, rel_path) VALUES (new.id, new.filename, new.rel_path);
        END;
    """)

    conn.commit()


def ensure_history_table(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS storage_history (
            date TEXT PRIMARY KEY,
            used_tb REAL NOT NULL
        );
    """)
    conn.commit()


def ensure_indexer_status_table(conn: sqlite3.Connection) -> None:
    """
    Guarda progresso do indexer para a interface.
    id sempre = 1
    """
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS indexer_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            processed INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0,
            start_time REAL,
            last_run INTEGER,
            last_finished_time REAL,
            last_duration_sec REAL,
            last_new INTEGER NOT NULL DEFAULT 0,
            last_updated INTEGER NOT NULL DEFAULT 0,
            last_deleted INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
        );
    """)
    cur.execute("INSERT OR IGNORE INTO indexer_status(id) VALUES (1);")
    conn.commit()


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None
