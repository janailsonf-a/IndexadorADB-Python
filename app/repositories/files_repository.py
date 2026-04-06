from app.repositories.db_connection import db_connect


class FilesRepository:
    @staticmethod
    def _build_filters(ext: str = "", area: str = ""):
        clauses = []
        params = []

        ext = (ext or "").strip().lower().lstrip(".")
        area = (area or "").strip().lower()

        if ext:
            clauses.append("REPLACE(LOWER(ext), '.', '') = ?")
            params.append(ext)

        if area:
            clauses.append("LOWER(rel_path) LIKE ?")
            params.append(f"{area}/%")

        where_sql = ""
        if clauses:
            where_sql = " AND " + " AND ".join(clauses)

        return where_sql, params

    def search_by_extension(
        self,
        ext_query: str,
        order_sql: str,
        page_size: int,
        offset: int,
        area: str = "",
    ):
        conn = db_connect()
        try:
            cur = conn.cursor()

            area = (area or "").strip().lower()

            extra_where = ""
            extra_params = []

            if area:
                extra_where += " AND LOWER(rel_path) LIKE ?"
                extra_params.append(f"{area}/%")

            total_matches = cur.execute(
                f"""
                SELECT COUNT(*) c
                FROM files_meta
                WHERE REPLACE(LOWER(ext), '.', '') = ?
                {extra_where}
                """,
                [ext_query, *extra_params],
            ).fetchone()["c"]

            rows = cur.execute(
                f"""
                SELECT filename, rel_path, ext,
                       ROUND(size_bytes/1024.0/1024.0, 2) AS size_mb,
                       created_at, modified_at
                FROM files_meta
                WHERE REPLACE(LOWER(ext), '.', '') = ?
                {extra_where}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
                """,
                [ext_query, *extra_params, page_size, offset],
            ).fetchall()

            return total_matches, rows
        finally:
            conn.close()

    def search_fts(
        self,
        fts_term: str,
        chosen_order: str,
        page_size: int,
        offset: int,
        ext: str = "",
        area: str = "",
    ):
        conn = db_connect()
        try:
            cur = conn.cursor()

            extra_where, extra_params = self._build_filters(ext=ext, area=area)

            total_matches = cur.execute(
                f"""
                SELECT COUNT(*) c
                FROM files
                JOIN files_meta m ON m.id = files.rowid
                WHERE files MATCH ?
                {extra_where}
                """,
                [fts_term, *extra_params],
            ).fetchone()["c"]

            rows = cur.execute(
                f"""
                SELECT m.filename, m.rel_path, m.ext,
                       ROUND(m.size_bytes/1024.0/1024.0, 2) AS size_mb,
                       m.created_at, m.modified_at
                FROM files
                JOIN files_meta m ON m.id = files.rowid
                WHERE files MATCH ?
                {extra_where}
                ORDER BY {chosen_order}
                LIMIT ? OFFSET ?
                """,
                [fts_term, *extra_params, page_size, offset],
            ).fetchall()

            return total_matches, rows
        finally:
            conn.close()

    def search_like(
        self,
        like_any: str,
        q_path: str,
        order_sql: str,
        page_size: int,
        offset: int,
        ext: str = "",
        area: str = "",
    ):
        conn = db_connect()
        try:
            cur = conn.cursor()

            base_where = "(filename LIKE ? OR rel_path LIKE ?)"
            extra_where, extra_params = self._build_filters(ext=ext, area=area)

            total_matches = cur.execute(
                f"""
                SELECT COUNT(*) c
                FROM files_meta
                WHERE {base_where}
                {extra_where}
                """,
                [like_any, q_path, *extra_params],
            ).fetchone()["c"]

            rows = cur.execute(
                f"""
                SELECT filename, rel_path, ext,
                       ROUND(size_bytes/1024.0/1024.0, 2) AS size_mb,
                       created_at, modified_at
                FROM files_meta
                WHERE {base_where}
                {extra_where}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
                """,
                [like_any, q_path, *extra_params, page_size, offset],
            ).fetchall()

            return total_matches, rows
        finally:
            conn.close()