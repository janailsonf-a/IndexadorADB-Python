import sqlite3
import time
from math import ceil
from urllib.parse import quote

from app.core.constants import PAGE_SIZE_DEFAULT, ROOT_DIR
from app.core.logger import logger
from app.path_converter import PathConverter, detectar_sistema
from app.repositories.status_repository import assert_db_root_dir, db_count_files
from app.repositories.files_repository import FilesRepository
from app.services.activity_service import ActivityService


class SearchService:
    def __init__(self):
        self.repository = FilesRepository()
        self.converter = PathConverter()

    @staticmethod
    def clamp_int(value, default: int, min_v: int, max_v: int) -> int:
        try:
            v = int(value)
        except Exception:
            return default
        return max(min_v, min(max_v, v))

    def search(self, request, query: str, page: int = 1, page_size: int = PAGE_SIZE_DEFAULT, order: str = "recent"):
        assert_db_root_dir()

        q_raw = (query or "").strip()
        q = q_raw
        q_lower = q_raw.lower()

        common_exts = {
            "txt", "pdf", "png", "jpg", "jpeg", "webp", "gif", "svg", "mp4", "webm", "mov", "mkv",
            "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "rar", "7z", "json", "csv", "log",
            "py", "js", "ts", "html", "css", "php", "java", "c", "cpp", "h", "md", "xml",
        }

        ext_query = None
        if q_lower.startswith(".") and len(q_lower) >= 2:
            ext_query = q_lower[1:]
        elif q_lower in common_exts:
            ext_query = q_lower

        total_indexed = db_count_files()
        page_size = self.clamp_int(page_size, PAGE_SIZE_DEFAULT, 5, 100)
        page = self.clamp_int(page, 1, 1, 100000)

        if (not ext_query) and len(q) < 2:
            return {
                "results": [],
                "last_query": q,
                "error": "Digite ao menos 2 caracteres.",
                "meta": {
                    "total_indexed": total_indexed,
                    "query_ms": None,
                    "total_matches": 0,
                    "page": 1,
                    "total_pages": 0,
                    "page_size": page_size,
                    "order": order,
                },
            }

        ActivityService.log("search", None, q)

        order_map = {
            "name_asc": "filename COLLATE NOCASE ASC",
            "name_desc": "filename COLLATE NOCASE DESC",
            "recent": "modified_at DESC",
            "oldest": "modified_at ASC",
            "size_desc": "size_bytes DESC, filename ASC",
            "type": "ext ASC, filename ASC",
        }
        order_sql = order_map.get(order, "modified_at DESC")

        offset = (page - 1) * page_size
        t0 = time.perf_counter()

        try:
            rows = []
            total_matches = 0
            using_fts = False

            if ext_query:
                total_matches, rows = self.repository.search_by_extension(
                    ext_query, order_sql, page_size, offset
                )
            else:
                tokens = "".join([ch if ch.isalnum() else " " for ch in q_lower]).split()
                fts_term = " ".join([f"{t}*" for t in tokens]) if tokens else f"{q}*"

                try:
                    total_matches, rows = self.repository.search_fts(
                        fts_term,
                        "bm25(files)" if order == "relevance" else order_sql,
                        page_size,
                        offset,
                    )
                    using_fts = total_matches > 0
                except sqlite3.OperationalError:
                    using_fts = False

                if not using_fts:
                    total_matches, rows = self.repository.search_like(
                        f"%{q}%",
                        "%" + "%".join(q.split()) + "%",
                        order_sql,
                        page_size,
                        offset,
                    )
        except sqlite3.OperationalError:
            logger.exception("Busca indisponível enquanto índice atualiza")
            return {
                "results": [],
                "last_query": q,
                "error": "⚙️ Índice atualizando...",
                "meta": {
                    "total_indexed": total_indexed,
                    "query_ms": None,
                    "total_matches": 0,
                    "page": 1,
                    "total_pages": 0,
                    "page_size": page_size,
                    "order": order,
                },
            }

        total_pages = ceil(total_matches / page_size) if total_matches > 0 else 0
        page = max(1, min(page, total_pages)) if total_pages > 0 else 1

        window = 2
        start_page = max(1, page - window)
        end_page = min(total_pages, page + window)
        if page <= 3:
            end_page = min(total_pages, 5)
        if page > total_pages - 3:
            start_page = max(1, total_pages - 4)
        pages_to_show = list(range(start_page, end_page + 1))

        sistema = detectar_sistema(request.headers.get("user-agent", ""))
        results = []

        for r in rows:
            caminho_linux = str(ROOT_DIR / r["rel_path"])
            caminho_publico = self.converter.gerar_caminho_publico(caminho_linux, sistema)
            results.append(
                {
                    "filename": r["filename"],
                    "rel_path": r["rel_path"],
                    "ext": r["ext"] or "",
                    "size_mb": r["size_mb"],
                    "created_at": r["created_at"],
                    "modified_at": r["modified_at"],
                    "preview_link": f"/files/{quote(r['rel_path'])}?disposition=inline",
                    "network_path": caminho_publico,
                }
            )

        query_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "results": results,
            "last_query": q,
            "error": "",
            "meta": {
                "total_indexed": total_indexed,
                "query_ms": query_ms,
                "total_matches": total_matches,
                "page": page,
                "total_pages": total_pages,
                "pages_to_show": pages_to_show,
                "page_size": page_size,
                "order": order if using_fts or order != "relevance" else "recent",
            },
        }