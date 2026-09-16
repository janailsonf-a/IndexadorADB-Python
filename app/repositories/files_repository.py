import sqlite3
from typing import Tuple, List

from app.core.constants import DB_PATH

# Teto do COUNT das buscas por texto. Contar exato (COUNT(DISTINCT) sobre a
# tabela inteira) era metade do custo da busca. Aqui contamos só até este teto
# (LIMIT dentro do count) — para termos frequentes o count para cedo; a UI
# mostra "N" ou "N+" e pagina até este limite. Navegação sem filtro não usa isto
# (usa o total real cacheado, ver SearchService.is_browse + list_all).
COUNT_CAP = 2000

# Colunas retornadas por todas as buscas. Tags vêm por subquery correlacionada
# (só as <=50 linhas da página), em vez de LEFT JOIN file_tags + GROUP BY sobre
# todos os matches — o JOIN explodia linhas e forçava agrupamento caro.
_SELECT_COLS = """
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
    fm.content_hash,
    (SELECT GROUP_CONCAT(t.tag, ',') FROM file_tags t WHERE t.file_id = fm.id) AS tags
"""


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
        return f"""
            SELECT
                {_SELECT_COLS}
            FROM files_meta fm
        """

    @staticmethod
    def _capped_count(conn: sqlite3.Connection, inner_sql: str, params: list) -> int:
        """
        Conta até COUNT_CAP linhas de inner_sql (que deve ser um SELECT sem
        ORDER BY). Evita o COUNT(DISTINCT) full-scan: para assim que atinge o
        teto. Retorna o número real quando < teto.
        """
        sql = f"SELECT COUNT(*) FROM ({inner_sql} LIMIT {COUNT_CAP})"
        return conn.execute(sql, params).fetchone()[0]

    @staticmethod
    def _extra_filters(campaign: str = "", date_from: str = "", date_to: str = "",
                       exts: str = "") -> Tuple[List[str], list]:
        """
        Filtros opcionais compartilhados pelos tres modos de busca (extensao,
        LIKE e FTS). Antes campanha/data/tipo eram filtrados no navegador, sobre
        a lista ja carregada — com a galeria paginada isso passou a filtrar so os
        50 itens da pagina atual, entao um filtro de 2023 na pagina 1 (que so tem
        2026) devolvia "nenhum arquivo".
        """
        where: List[str] = []
        params: list = []

        if campaign:
            where.append("COALESCE(fm.campaign, '') = ?")
            params.append(campaign)

        # modified_at e created_at sao TEXT no formato "YYYY-MM-DD HH:MM".
        # Comparar so os 10 primeiros caracteres evita o off-by-one de
        # "2023-12-31 14:30" > "2023-12-31" excluir o proprio dia final.
        date_col = "substr(COALESCE(fm.modified_at, fm.created_at, ''), 1, 10)"
        if date_from:
            where.append(f"{date_col} >= ?")
            params.append(date_from)
        if date_to:
            where.append(f"{date_col} <= ?")
            params.append(date_to)

        # lista de extensoes da categoria escolhida (imagens, videos...). O
        # mapeamento categoria->extensoes vive no front (useFileType), que manda
        # as extensoes ja resolvidas — evita duplicar a tabela aqui.
        ext_list = [e.strip().lower().lstrip(".") for e in (exts or "").split(",") if e.strip()]
        if ext_list:
            marks = ",".join("?" for _ in ext_list)
            where.append(f"LOWER(COALESCE(fm.ext, '')) IN ({marks})")
            params.extend(ext_list)

        return where, params

    def list_all(
        self,
        order_sql: str,
        limit: int,
        offset: int,
    ) -> List[sqlite3.Row]:
        """
        Navegação do Acervo sem filtro (query vazia). Varre files_meta pela
        coluna ordenada (indexada) e pega só a página; tags por subquery das
        <=50 linhas. O total vem do count cacheado (sem filtro, total de
        resultados = total de arquivos).
        """
        conn = self._connect()
        try:
            data_sql = f"""
                SELECT
                    {_SELECT_COLS}
                FROM files_meta fm
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
            """
            return conn.execute(data_sql, [limit, offset]).fetchall()
        finally:
            conn.close()

    def search_by_extension(
        self,
        ext_query: str,
        order_sql: str,
        limit: int,
        offset: int,
        area: str = "",
        campaign: str = "",
        date_from: str = "",
        date_to: str = "",
        exts: str = "",
    ) -> Tuple[int, List[sqlite3.Row]]:
        conn = self._connect()
        try:
            where = ["LOWER(COALESCE(fm.ext, '')) = ?"]
            params = [ext_query.lower()]

            if area:
                where.append(f"{self._area_sql()} = ?")
                params.append(area.lower())

            extra_where, extra_params = self._extra_filters(campaign, date_from, date_to, exts)
            where.extend(extra_where)
            params.extend(extra_params)

            where_sql = " AND ".join(where)

            total = self._capped_count(
                conn, f"SELECT 1 FROM files_meta fm WHERE {where_sql}", params
            )

            data_sql = f"""
                SELECT
                    {_SELECT_COLS}
                FROM files_meta fm
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
            """
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
        campaign: str = "",
        date_from: str = "",
        date_to: str = "",
        exts: str = "",
    ) -> Tuple[int, List[sqlite3.Row]]:
        conn = self._connect()
        try:
            # Tag por EXISTS (não JOIN) p/ não explodir linhas. Dois grupos:
            # termo cru e termo com espaços colapsados.
            where = [
                """
                (
                    fm.filename LIKE ?
                    OR fm.rel_path LIKE ?
                    OR COALESCE(fm.title, '') LIKE ?
                    OR COALESCE(fm.description, '') LIKE ?
                    OR COALESCE(fm.campaign, '') LIKE ?
                    OR COALESCE(fm.status, '') LIKE ?
                    OR EXISTS(SELECT 1 FROM file_tags ft WHERE ft.file_id = fm.id AND ft.tag LIKE ?)
                    OR fm.filename LIKE ?
                    OR fm.rel_path LIKE ?
                    OR COALESCE(fm.title, '') LIKE ?
                    OR COALESCE(fm.description, '') LIKE ?
                    OR COALESCE(fm.campaign, '') LIKE ?
                    OR COALESCE(fm.status, '') LIKE ?
                    OR EXISTS(SELECT 1 FROM file_tags ft WHERE ft.file_id = fm.id AND ft.tag LIKE ?)
                )
                """
            ]

            params = [like_query] * 7 + [like_spaced_query] * 7

            if ext:
                where.append("LOWER(COALESCE(fm.ext, '')) = ?")
                params.append(ext.lower())

            if area:
                where.append(f"{self._area_sql()} = ?")
                params.append(area.lower())

            extra_where, extra_params = self._extra_filters(campaign, date_from, date_to, exts)
            where.extend(extra_where)
            params.extend(extra_params)

            where_sql = " AND ".join(where)

            total = self._capped_count(
                conn, f"SELECT 1 FROM files_meta fm WHERE {where_sql}", params
            )

            data_sql = f"""
                SELECT
                    {_SELECT_COLS}
                FROM files_meta fm
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
            """
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
        campaign: str = "",
        date_from: str = "",
        date_to: str = "",
        exts: str = "",
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

            extra_where, extra_params = self._extra_filters(campaign, date_from, date_to, exts)
            where.extend(extra_where)
            params.extend(extra_params)

            where_sql = " AND ".join(where)

            # MATCH dá rowids distintos; sem o LEFT JOIN file_tags não há
            # duplicata, então nada de GROUP BY. Tags vêm por subquery.
            from_join = "files JOIN files_meta fm ON fm.id = files.rowid"

            total = self._capped_count(
                conn, f"SELECT 1 FROM {from_join} WHERE {where_sql}", params
            )

            data_sql = f"""
                SELECT
                    {_SELECT_COLS}
                FROM {from_join}
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(data_sql, params + [limit, offset]).fetchall()
            return total, rows
        finally:
            conn.close()

    def find_duplicate_hashes(self, limit: int = 200) -> List[sqlite3.Row]:
        """Hashes de conteúdo com mais de 1 arquivo, maiores grupos primeiro."""
        conn = self._connect()
        try:
            sql = """
                SELECT content_hash, COUNT(*) AS qty
                FROM files_meta
                WHERE content_hash IS NOT NULL AND content_hash != '' AND size_bytes > 0
                GROUP BY content_hash
                HAVING COUNT(*) > 1
                ORDER BY qty DESC
                LIMIT ?
            """
            return conn.execute(sql, (limit,)).fetchall()
        finally:
            conn.close()

    def files_by_content_hashes(self, hashes: List[str]) -> List[sqlite3.Row]:
        if not hashes:
            return []
        conn = self._connect()
        try:
            placeholders = ",".join("?" for _ in hashes)
            sql = f"""
                SELECT
                    {_SELECT_COLS}
                FROM files_meta fm
                WHERE fm.content_hash IN ({placeholders})
                ORDER BY fm.content_hash, fm.modified_at DESC
            """
            return conn.execute(sql, hashes).fetchall()
        finally:
            conn.close()
