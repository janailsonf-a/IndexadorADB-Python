import sqlite3
from typing import Tuple, List

from app.core.constants import DB_PATH


class FilesRepository:
    def __init__(self):
        self.db_path = str(DB_PATH)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @staticmethod
    def _area_sql() -> str:
        return "LOWER(substr(fm.rel_path, 1, instr(fm.rel_path || '/', '/') - 1))"

    @staticmethod
    def _base_select_sql() -> str:
        return """
            SELECT
                fm.id,
                fm.filename,
                fm.rel_path,
                fm.ext,
                ROUND(fm.size_bytes / 1024.0 / 1024.0, 2) AS size_mb,
                fm.created_at,
                fm.modified_at,
                fm.title,
                fm.description,
                fm.campaign,
                fm.status,
                fm.is_official,
                GROUP_CONCAT(ft.tag, ',') AS tags
            FROM files_meta fm
            LEFT JOIN file_tags ft ON ft.file_id = fm.id
        """

    @staticmethod
    def _group_by_sql() -> str:
        return """
            GROUP BY
                fm.id,
                fm.filename,
                fm.rel_path,
                fm.ext,
                fm.size_bytes,
                fm.created_at,
                fm.modified_at,
                fm.title,
                fm.description,
                fm.campaign,
                fm.status,
                fm.is_official
        """

    def search_by_extension(
        self,
        ext_query: str,
        order_sql: str,
        limit: int,
        offset: int,
        area: str = "",
    ) -> Tuple[int, List[sqlite3.Row]]:
        conn = self._connect()
        try:
            where = ["LOWER(COALESCE(fm.ext, '')) = ?"]
            params = [ext_query.lower()]

            if area:
                where.append(f"{self._area_sql()} = ?")
                params.append(area.lower())

            where_sql = " AND ".join(where)

            count_sql = f"""
                SELECT COUNT(DISTINCT fm.id)
                FROM files_meta fm
                LEFT JOIN file_tags ft ON ft.file_id = fm.id
                WHERE {where_sql}
            """

            data_sql = f"""
                {self._base_select_sql()}
                WHERE {where_sql}
                {self._group_by_sql()}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
            """

            total = conn.execute(count_sql, params).fetchone()[0]
            rows = conn.execute(data_sql, params + [limit, offset]).fetchall()
            return total, rows
        finally:
            conn.close()

    def search_like(
        self,
        like_query: str,
        like_spaced_query: str,
        order_sql: str,
        limit: int,
        offset: int,
        ext: str = "",
        area: str = "",
    ) -> Tuple[int, List[sqlite3.Row]]:
        conn = self._connect()
        try:
            where = [
                """
                (
                    fm.filename LIKE ?
                    OR fm.rel_path LIKE ?
                    OR COALESCE(fm.title, '') LIKE ?
                    OR COALESCE(fm.description, '') LIKE ?
                    OR COALESCE(fm.campaign, '') LIKE ?
                    OR COALESCE(fm.status, '') LIKE ?
                    OR COALESCE(ft.tag, '') LIKE ?
                    OR fm.filename LIKE ?
                    OR fm.rel_path LIKE ?
                    OR COALESCE(fm.title, '') LIKE ?
                    OR COALESCE(fm.description, '') LIKE ?
                    OR COALESCE(fm.campaign, '') LIKE ?
                    OR COALESCE(fm.status, '') LIKE ?
                    OR COALESCE(ft.tag, '') LIKE ?
                )
                """
            ]

            params = [
                like_query, like_query, like_query, like_query, like_query, like_query, like_query,
                like_spaced_query, like_spaced_query, like_spaced_query, like_spaced_query,
                like_spaced_query, like_spaced_query, like_spaced_query,
            ]

            if ext:
                where.append("LOWER(COALESCE(fm.ext, '')) = ?")
                params.append(ext.lower())

            if area:
                where.append(f"{self._area_sql()} = ?")
                params.append(area.lower())

            where_sql = " AND ".join(where)

            count_sql = f"""
                SELECT COUNT(DISTINCT fm.id)
                FROM files_meta fm
                LEFT JOIN file_tags ft ON ft.file_id = fm.id
                WHERE {where_sql}
            """

            data_sql = f"""
                {self._base_select_sql()}
                WHERE {where_sql}
                {self._group_by_sql()}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
            """

            total = conn.execute(count_sql, params).fetchone()[0]
            rows = conn.execute(data_sql, params + [limit, offset]).fetchall()
            return total, rows
        finally:
            conn.close()

    def search_fts(
        self,
        fts_term: str,
        order_sql: str,
        limit: int,
        offset: int,
        ext: str = "",
        area: str = "",
    ) -> Tuple[int, List[sqlite3.Row]]:
        conn = self._connect()
        try:
            where = ["files MATCH ?"]
            params = [fts_term]

            if ext:
                where.append("LOWER(COALESCE(fm.ext, '')) = ?")
                params.append(ext.lower())

            if area:
                where.append(f"{self._area_sql()} = ?")
                params.append(area.lower())

            where_sql = " AND ".join(where)

            count_sql = f"""
                SELECT COUNT(DISTINCT fm.id)
                FROM files
                JOIN files_meta fm ON fm.id = files.rowid
                LEFT JOIN file_tags ft ON ft.file_id = fm.id
                WHERE {where_sql}
            """

            data_sql = f"""
                SELECT
                    fm.id,
                    fm.filename,
                    fm.rel_path,
                    fm.ext,
                    ROUND(fm.size_bytes / 1024.0 / 1024.0, 2) AS size_mb,
                    fm.created_at,
                    fm.modified_at,
                    fm.title,
                    fm.description,
                    fm.campaign,
                    fm.status,
                    fm.is_official,
                    GROUP_CONCAT(ft.tag, ',') AS tags
                FROM files
                JOIN files_meta fm ON fm.id = files.rowid
                LEFT JOIN file_tags ft ON ft.file_id = fm.id
                WHERE {where_sql}
                GROUP BY
                    fm.id,
                    fm.filename,
                    fm.rel_path,
                    fm.ext,
                    fm.size_bytes,
                    fm.created_at,
                    fm.modified_at,
                    fm.title,
                    fm.description,
                    fm.campaign,
                    fm.status,
                    fm.is_official
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
            """

            total = conn.execute(count_sql, params).fetchone()[0]
            rows = conn.execute(data_sql, params + [limit, offset]).fetchall()
            return total, rows
        finally:
            conn.close()