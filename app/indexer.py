import os
import time
import fcntl
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Tuple, Set, List

from app.config import settings
from app.utils import path_hash
from app.db import connect, ensure_files_schema, ensure_indexer_status_table, set_meta


@dataclass
class RunStats:
    scanned: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0


ROOT_DIR = os.path.abspath(settings.root_dir)
DB_PATH = settings.db_path

IGNORE_DIRS: Set[str] = {
    ".cache", ".local", ".Trash", ".venv",
    "node_modules", "__pycache__", ".git",
    "snap", "tmp", "Temp",
    ".config", ".mozilla", ".thumbnails",
    ".npm", ".cargo", ".steam",
    "proc", "sys", "dev", "run",
}

TEMP_SUFFIXES = (".swp", ".tmp", ".part", ".crdownload", ".download", "~")

LOCK_FILE = "/tmp/enterprise_file_indexer.lock"
BATCH_SIZE = 3000


def _ext(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    return ext if ext else "sem_ext"



def _fmt_dt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class SingleInstanceLock:
    def __init__(self, lock_path: str = LOCK_FILE):
        self.lock_path = lock_path
        self.fp = None

    def __enter__(self):
        self.fp = open(self.lock_path, "w")
        try:
            fcntl.flock(self.fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Outro indexador já está rodando (lock ativo).")
        self.fp.write(str(os.getpid()))
        self.fp.flush()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.fp:
            return
        try:
            fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)
        finally:
            self.fp.close()


def _should_ignore(rel_path: str) -> bool:
    base = os.path.basename(rel_path)

    # nunca indexar o db sqlite (e wal/shm)
    if base.startswith(os.path.basename(DB_PATH)):
        return True

    if base.endswith(TEMP_SUFFIXES):
        return True

    parts = rel_path.split(os.sep)
    return any(p in IGNORE_DIRS for p in parts)


def _estimate_total_files() -> int:
    total = 0
    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for name in files:
            rel_path = os.path.relpath(os.path.join(root, name), ROOT_DIR)
            if _should_ignore(rel_path):
                continue
            total += 1
    return total


def _print_banner(total_est: int) -> None:
    print("\n" + "─" * 48)
    print("INDEXER")
    print("─" * 48)
    print(f" Root Path : {ROOT_DIR}")
    print(f" DB Path   : {DB_PATH}")
    print(" Mode      : (incremental writes)")
    print(f" Started   : {_now_str()}")
    print(f" Files Est : {total_est:,}".replace(",", "."))
    print("─" * 48 + "\n")


def index_files() -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

    with SingleInstanceLock():
        conn = connect(DB_PATH)
        ensure_files_schema(conn)
        ensure_indexer_status_table(conn)
        set_meta(conn, "root_dir", ROOT_DIR)

        cur = conn.cursor()

        existing: Dict[str, Tuple[int, int]] = {}
        for r in cur.execute("SELECT id, rel_path, mtime_ns FROM files_meta"):
            existing[r["rel_path"]] = (int(r["id"]), int(r["mtime_ns"] or 0))

        run_id = int(time.time())
        total_est = _estimate_total_files()
        _print_banner(total_est)

        stats = RunStats()
        t0 = time.time()

        # inicializa status para interface
        cur.execute("""
            UPDATE indexer_status
               SET processed=0,
                   total=?,
                   start_time=?,
                   last_run=?,
                   last_error=NULL
             WHERE id=1
        """, (total_est, t0, run_id))
        conn.commit()

        to_touch: List[Tuple[int, int]] = []
        to_update: List[Tuple[str, str, int, str, str, int, int, str]] = []
        to_insert: List[Tuple[str, str, str, int, str, str, str, int, int]] = []

        scanned = 0
        last_status_write = time.time()

        def flush() -> None:
            nonlocal to_touch, to_update, to_insert, last_status_write

            if to_insert:
                cur.executemany("""
                    INSERT INTO files_meta
                    (filename, rel_path, ext, size_bytes, created_at, modified_at, path_hash, mtime_ns, last_seen_run)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, to_insert)
                to_insert = []

            if to_update:
                cur.executemany("""
                    UPDATE files_meta SET
                        filename=?,
                        ext=?,
                        size_bytes=?,
                        modified_at=?,
                        created_at=?,
                        mtime_ns=?,
                        last_seen_run=?
                    WHERE rel_path=?
                """, to_update)
                to_update = []

            if to_touch:
                cur.executemany("UPDATE files_meta SET last_seen_run=? WHERE id=?", to_touch)
                to_touch = []

            # atualiza status (não a cada arquivo, só no flush)
            cur.execute("""
                UPDATE indexer_status
                   SET processed=?,
                       total=?,
                       start_time=?
                 WHERE id=1
            """, (scanned, total_est, t0))

            conn.commit()
            last_status_write = time.time()

        for root, dirs, files in os.walk(ROOT_DIR):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for name in files:
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, ROOT_DIR)

                if _should_ignore(rel_path):
                    continue

                scanned += 1
                stats.scanned += 1

                try:
                    st = os.stat(full_path)
                except Exception:
                    continue

                filename = os.path.basename(rel_path)
                ext = _ext(filename)
                size_bytes = int(st.st_size)
                modified_at = _fmt_dt(st.st_mtime)
                created_at = modified_at
                mtime_ns = int(getattr(st, "st_mtime_ns", st.st_mtime * 1_000_000_000))

                hit = existing.get(rel_path)

                if hit:
                    _id, old_mtime = hit
                    if old_mtime == mtime_ns:
                        stats.unchanged += 1
                        to_touch.append((run_id, _id))
                    else:
                        stats.updated += 1
                        to_update.append((
                            filename, ext, size_bytes,
                            modified_at, created_at,
                            mtime_ns, run_id, rel_path
                        ))
                        existing[rel_path] = (_id, mtime_ns)
                else:
                    stats.new += 1
                    to_insert.append((
                        filename, rel_path, ext, size_bytes,
                        created_at, modified_at,
                        path_hash(rel_path), mtime_ns, run_id
                    ))

                if (len(to_touch) + len(to_update) + len(to_insert)) >= BATCH_SIZE:
                    flush()

                if scanned % 5000 == 0 and total_est:
                    elapsed = max(0.001, time.time() - t0)
                    speed = scanned / elapsed
                    pct = (scanned / total_est) * 100
                    print((
                        f" Progress: {pct:5.1f}% | {scanned:7,d} scanned | "
                        f"{speed:7.0f} files/sec | +{stats.new} new, ~{stats.updated} upd"
                    ).replace(",", "."))

                # segurança: se ficar muito tempo sem flush (muito arquivo "unchanged"), ainda atualiza status
                if (time.time() - last_status_write) > 2.5:
                    flush()

        flush()

        # remove deletados
        cur.execute("DELETE FROM files_meta WHERE last_seen_run < ?", (run_id,))
        stats.deleted = cur.rowcount if cur.rowcount != -1 else 0
        conn.commit()

        duration = time.time() - t0

        cur.execute("""
            UPDATE indexer_status
               SET processed=?,
                   total=?,
                   last_finished_time=?,
                   last_duration_sec=?,
                   last_new=?,
                   last_updated=?,
                   last_deleted=?,
                   last_error=NULL
             WHERE id=1
        """, (
            scanned, total_est,
            time.time(), duration,
            stats.new, stats.updated, stats.deleted
        ))
        conn.commit()

        print("\n" + "─" * 48)
        print(" Indexing Completed Successfully")
        print("─" * 48)
        print(f" Scanned    : {stats.scanned:,}".replace(",", "."))
        print(f" New        : {stats.new:,}".replace(",", "."))
        print(f" Updated    : {stats.updated:,}".replace(",", "."))
        print(f" Unchanged  : {stats.unchanged:,}".replace(",", "."))
        print(f" Deleted    : {stats.deleted:,}".replace(",", "."))
        print(f" Duration   : {duration:.1f} sec")
        print(" Status     : OK")
        print("─" * 48 + "\n")

        conn.close()


if __name__ == "__main__":
    try:
        index_files()
    except Exception as e:
        # registra erro no status, sem derrubar “silenciosamente”
        try:
            conn = connect(DB_PATH)
            ensure_indexer_status_table(conn)
            conn.execute("UPDATE indexer_status SET last_error=? WHERE id=1", (str(e),))
            conn.commit()
            conn.close()
        except Exception:
            pass
        raise
