def create_tables(conn):
    cur = conn.cursor()

    # Tabela principal (controle único)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS files_meta (
        id INTEGER PRIMARY KEY,
        path_hash TEXT UNIQUE,
        filename TEXT,
        rel_path TEXT,
        ext TEXT,
        size_mb REAL,
        created_at TEXT,
        modified_at TEXT,
        last_indexed TEXT
    )
    """)

    # FTS apenas para busca
    cur.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS files USING fts5(
        filename,
        rel_path,
        ext,
        content='files_meta',
        content_rowid='id'
    )
    """)


def ensure_indexer_status(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS indexer_status (
            id INTEGER PRIMARY KEY CHECK (id=1),
            processed INTEGER,
            total INTEGER,
            start_time REAL
        )
    """)
    conn.execute("""
        INSERT OR IGNORE INTO indexer_status (id, processed, total, start_time)
        VALUES (1,0,0,0)
    """)
    conn.commit()
