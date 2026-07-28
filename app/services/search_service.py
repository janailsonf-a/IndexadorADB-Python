import sqlite3
import time
from math import ceil
from urllib.parse import quote

from app.core.constants import PAGE_SIZE_DEFAULT, ROOT_DIR
from app.core.logger import logger
from app.path_converter import PathConverter, detectar_sistema
from app.repositories.files_repository import FilesRepository
from app.repositories.status_repository import assert_db_root_dir, db_count_files
from app.schemas.search import (
    SearchMeta,
    SearchResponse,
    SearchResultItem,
    DuplicateGroup,
    DuplicatesResponse,
)
from app.services.activity_service import ActivityService
from app.services.thumbnail_service import ThumbnailService


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

    @staticmethod
    def _normalize_area(rel_path: str) -> str:
        if not rel_path:
            return "Geral"
        first = rel_path.split("/")[0].strip()
        return first if first else "Geral"

    @staticmethod
    def _parse_tags(raw_tags: str | None) -> list[str]:
        if not raw_tags:
            return []

        seen = set()
        items = []

        for tag in raw_tags.split(","):
            clean = tag.strip()
            if clean and clean not in seen:
                seen.add(clean)
                items.append(clean)

        return items

    @staticmethod
    def _extract_bearer_token(request: object) -> str:
        """
        Pega o JWT cru do header Authorization pra embutir em preview_link/
        download_link — esses links são usados em <img>/<a>/<iframe>/<audio>,
        que nunca mandam header customizado, só o axios do app manda Bearer
        de verdade na hora de buscar. Sem isso o navegador recebe 401 ao
        tentar carregar qualquer preview de arquivo.
        """
        auth_header = getattr(request, "headers", {}).get("authorization", "") or ""
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:]
        return ""

    def _build_results(self, request: object, rows) -> list[SearchResultItem]:
        sistema = detectar_sistema(getattr(request, "headers", {}).get("user-agent", ""))
        token = self._extract_bearer_token(request)
        token_qs = f"&token={quote(token)}" if token else ""
        results = []

        for r in rows:
            rel_path = r["rel_path"]
            caminho_linux = str(ROOT_DIR / rel_path)
            caminho_publico = self.converter.gerar_caminho_publico(caminho_linux, sistema)

            results.append(
                SearchResultItem(
                    id=str(r["id"]),
                    filename=r["filename"],
                    rel_path=rel_path,
                    full_path=caminho_publico,
                    ext=r["ext"] or "",
                    area=self._normalize_area(rel_path),
                    size_mb=r["size_mb"],
                    created_at=r["created_at"],
                    modified_at=r["modified_at"],
                    preview_link=f"/files/{quote(rel_path)}?disposition=inline{token_qs}",
                    download_link=f"/download?path={quote(rel_path)}{token_qs}",
                    thumbnail_link=(
                        f"/api/thumbnail?path={quote(rel_path)}{token_qs}"
                        if ThumbnailService.is_video(r["filename"])
                        else None
                    ),
                    title=r["title"],
                    description=r["description"],
                    campaign=r["campaign"],
                    status=r["status"],
                    is_official=bool(r["is_official"]),
                    tags=self._parse_tags(r["tags"]),
                    content_hash=r["content_hash"],
                )
            )

        return results

    def duplicates(self, request: object, limit_groups: int = 200) -> DuplicatesResponse:
        hash_rows = self.repository.find_duplicate_hashes(limit=limit_groups)
        hashes = [row["content_hash"] for row in hash_rows]
        file_rows = self.repository.files_by_content_hashes(hashes)
        items = self._build_results(request, file_rows)

        by_hash: dict[str, list[SearchResultItem]] = {}
        for item in items:
            by_hash.setdefault(item.content_hash, []).append(item)

        groups = [
            DuplicateGroup(content_hash=h, count=len(by_hash.get(h, [])), files=by_hash.get(h, []))
            for h in hashes
            if by_hash.get(h)
        ]

        return DuplicatesResponse(
            groups=groups,
            total_groups=len(groups),
            total_files=sum(g.count for g in groups),
        )

    def search_core(
        self,
        request,
        query: str,
        page: int = 1,
        page_size: int = PAGE_SIZE_DEFAULT,
        order: str = "recent",
        ext: str = "",
        area: str = "",
        current_user: dict | None = None,
    ):
        assert_db_root_dir()

        q_raw = (query or "").strip()
        q = q_raw
        q_lower = q_raw.lower()

        ext = (ext or "").strip().lower().lstrip(".")
        area = (area or "").strip().lower()

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

        if (not ext_query) and len(q) < 2 and not ext and not area and q:
            return {
                "rows": [],
                "last_query": q,
                "error": "Digite ao menos 2 caracteres.",
                "meta": {
                    "total_indexed": total_indexed,
                    "query_ms": None,
                    "total_matches": 0,
                    "page": 1,
                    "total_pages": 0,
                    "pages_to_show": [],
                    "page_size": page_size,
                    "order": order,
                },
            }

        ActivityService.log(
            action="search",
            filename=None,
            rel_path=q or f"ext:{ext} area:{area}",
            current_user=current_user,
        )

        order_map = {
            "name_asc": "fm.filename COLLATE NOCASE ASC",
            "name_desc": "fm.filename COLLATE NOCASE DESC",
            "recent": "fm.modified_at DESC",
            "oldest": "fm.modified_at ASC",
            "size_desc": "fm.size_bytes DESC, fm.filename ASC",
            "type": "fm.ext ASC, fm.filename ASC",
            "relevance": "bm25(files)",
        }
        order_sql = order_map.get(order, "fm.modified_at DESC")

        offset = (page - 1) * page_size
        t0 = time.perf_counter()

        try:
            rows = []
            total_matches = 0
            using_fts = False

            if ext_query:
                total_matches, rows = self.repository.search_by_extension(
                    ext_query=ext_query,
                    order_sql=order_map.get(order, "fm.modified_at DESC").replace("bm25(files)", "fm.modified_at DESC"),
                    limit=page_size,
                    offset=offset,
                    area=area,
                )
            else:
                tokens = "".join([ch if ch.isalnum() else " " for ch in q_lower]).split()
                fts_term = " ".join([f"{t}*" for t in tokens]) if tokens else f"{q}*"

                try:
                    total_matches, rows = self.repository.search_fts(
                        fts_term=fts_term,
                        order_sql=order_sql,
                        limit=page_size,
                        offset=offset,
                        ext=ext,
                        area=area,
                    )
                    using_fts = total_matches > 0
                except sqlite3.OperationalError:
                    using_fts = False

                if not using_fts:
                    fallback_order_sql = order_map.get(order, "fm.modified_at DESC").replace(
                        "bm25(files)", "fm.modified_at DESC"
                    )
                    total_matches, rows = self.repository.search_like(
                        like_query=f"%{q}%",
                        like_spaced_query="%" + "%".join(q.split()) + "%",
                        order_sql=fallback_order_sql,
                        limit=page_size,
                        offset=offset,
                        ext=ext,
                        area=area,
                    )

        except sqlite3.OperationalError as exc:
            logger.exception("Busca indisponível por erro operacional no SQLite: %s", exc)
            return {
                "rows": [],
                "last_query": q,
                "error": "Não foi possível consultar o índice agora.",
                "meta": {
                    "total_indexed": total_indexed,
                    "query_ms": None,
                    "total_matches": 0,
                    "page": 1,
                    "total_pages": 0,
                    "pages_to_show": [],
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
        if total_pages > 0 and page > total_pages - 3:
            start_page = max(1, total_pages - 4)
        pages_to_show = list(range(start_page, end_page + 1)) if total_pages > 0 else []

        query_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "rows": rows,
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

    def search_api(
        self,
        request,
        query: str = "",
        page: int = 1,
        page_size: int = PAGE_SIZE_DEFAULT,
        order: str = "recent",
        ext: str = "",
        area: str = "",
        current_user: dict | None = None,
    ) -> SearchResponse:
        payload = self.search_core(
            request=request,
            query=query,
            page=page,
            page_size=page_size,
            order=order,
            ext=ext,
            area=area,
            current_user=current_user,
        )

        rows = payload["rows"]
        meta_data = payload["meta"]

        results = self._build_results(request, rows)

        meta = SearchMeta(
            total_indexed=meta_data["total_indexed"],
            total_matches=meta_data["total_matches"],
            query_ms=meta_data["query_ms"],
            page=meta_data["page"],
            total_pages=meta_data["total_pages"],
            page_size=meta_data["page_size"],
            order=meta_data["order"],
            pages_to_show=meta_data["pages_to_show"],
        )

        return SearchResponse(
            results=results,
            meta=meta,
            error=payload["error"],
            last_query=payload["last_query"],
        )

    def search(
        self,
        request,
        query: str,
        page: int = 1,
        page_size: int = PAGE_SIZE_DEFAULT,
        order: str = "recent",
        current_user: dict | None = None,
    ):
        payload = self.search_core(
            request=request,
            query=query,
            page=page,
            page_size=page_size,
            order=order,
            current_user=current_user,
        )

        results = self._build_results(request, payload["rows"])

        return {
            "results": [item.model_dump() for item in results],
            "last_query": payload["last_query"],
            "error": payload["error"],
            "meta": payload["meta"],
        }