import os
import time
import sqlite3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.config import settings
from app.db import connect

ROOT_DIR = os.path.abspath(settings.root_dir)
DB_PATH = settings.db_path

# evita indexações duplicadas
DEBOUNCE_SECONDS = 1
last_event_time = {}


# ===============================
# DB
# ===============================
def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# ===============================
# INDEXAÇÃO INDIVIDUAL
# ===============================
def index_file(full_path, rel_path):
    try:
        stat = os.stat(full_path)
        conn = db_connect()

        conn.execute(
            """
            INSERT INTO files_meta (rel_path, filename, ext, size_bytes, modified_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(rel_path) DO UPDATE SET
                size_bytes=excluded.size_bytes,
                modified_at=excluded.modified_at
        """,
            (
                rel_path,
                os.path.basename(rel_path),
                os.path.splitext(rel_path)[1].lower(),
                stat.st_size,
                int(stat.st_mtime),
                int(stat.st_ctime),
            ),
        )

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Erro ao indexar {rel_path}: {e}")


def remove_file(rel_path):
    try:
        conn = db_connect()
        conn.execute("DELETE FROM files_meta WHERE rel_path=?", (rel_path,))
        conn.commit()
        conn.close()
        print(f"Removed: {rel_path}")
    except Exception as e:
        print(f"Erro ao remover {rel_path}: {e}")


# ===============================
# ANTI DUPLICAÇÃO
# ===============================
def safe_index(full_path, rel_path):
    now = time.time()

    if rel_path in last_event_time:
        if now - last_event_time[rel_path] < DEBOUNCE_SECONDS:
            return

    last_event_time[rel_path] = now
    index_file(full_path, rel_path)
    print(f"Indexed: {rel_path}")


# ===============================
# WATCHDOG HANDLER
# ===============================
class WatcherHandler(FileSystemEventHandler):

    def on_created(self, event):
        if not event.is_directory:
            rel_path = os.path.relpath(event.src_path, ROOT_DIR)
            safe_index(event.src_path, rel_path)

    def on_modified(self, event):
        if not event.is_directory:
            rel_path = os.path.relpath(event.src_path, ROOT_DIR)
            safe_index(event.src_path, rel_path)

    def on_deleted(self, event):
        if not event.is_directory:
            rel_path = os.path.relpath(event.src_path, ROOT_DIR)
            remove_file(rel_path)


# ===============================
# RUN WATCHER
# ===============================
def start_watcher():
    print("Watcher ativo...")
    observer = Observer()
    handler = WatcherHandler()
    observer.schedule(handler, ROOT_DIR, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


if __name__ == "__main__":
    start_watcher()
