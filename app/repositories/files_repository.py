import sqlite3

from app.repositories.db_connection import db_connect


class FilesRepository:
    def search_by_extension(self, ext_query: str, order_sql: str, page_size: int, offset: int):
        conn = db_connect()
        try:
            cur = conn.cursor()
            total_matches = cur.execute(
                "SELECT COUNT(*) c FROM files_meta WHERE REPLACE(LOWER(ext), '.', '') = ?",
                (ext_query,),
            ).fetchone()["c"]

            rows = cur.execute(
                f"""
                SELECT filename, rel_path, ext,
                       ROUND(size_bytes/1024.0/1024.0, 2) AS size_mb,
                       created_at, modified_at
                FROM files_meta
                WHERE REPLACE(LOWER(ext), '.', '') = ?
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
                """,
                (ext_query, page_size, offset),
            ).fetchall()

            return total_matches, rows
        finally:
            conn.close()

    def search_fts(self, fts_term: str, chosen_order: str, page_size: int, offset: int):
        conn = db_connect()
        try:
            cur = conn.cursor()
            total_matches = cur.execute(
                "SELECT COUNT(*) c FROM files WHERE files MATCH ?",
                (fts_term,),
            ).fetchone()["c"]

            rows = cur.execute(
                f"""
                SELECT m.filename, m.rel_path, m.ext,
                       ROUND(m.size_bytes/1024.0/1024.0, 2) AS size_mb,
                       m.created_at, m.modified_at
                FROM files
                JOIN files_meta m ON m.id = files.rowid
                WHERE files MATCH ?
                ORDER BY {chosen_order}
                LIMIT ? OFFSET ?
                """,
                (fts_term, page_size, offset),
            ).fetchall()

            return total_matches, rows
        finally:
            conn.close()

    def search_like(self, like_any: str, q_path: str, order_sql: str, page_size: int, offset: int):
        conn = db_connect()
        try:
            cur = conn.cursor()
            where_sql = "filename LIKE ? OR rel_path LIKE ?"

            total_matches = cur.execute(
                f"SELECT COUNT(*) c FROM files_meta WHERE {where_sql}",
                (like_any, q_path),
            ).fetchone()["c"]

            rows = cur.execute(
                f"""
                SELECT filename, rel_path, ext,
                       ROUND(size_bytes/1024.0/1024.0, 2) AS size_mb,
                       created_at, modified_at
                FROM files_meta
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
                """,
                (like_any, q_path, page_size, offset),
            ).fetchall()

            return total_matches, rows
        finally:
            conn.close()