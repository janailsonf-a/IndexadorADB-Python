import os
import sqlite3
import shutil
import subprocess
import time
from math import ceil
from datetime import datetime
from typing import Any
from urllib.parse import quote
from app.path_converter import PathConverter, detectar_sistema
from app.config import settings

converter = PathConverter()

from datetime import datetime
from zoneinfo import ZoneInfo

BR_TZ = ZoneInfo("America/Sao_Paulo")

import psutil
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from urllib.parse import unquote

from app.config import settings
from app.db import (
    connect,
    get_meta,
    ensure_files_schema,
    ensure_history_table,
    ensure_indexer_status_table,
)

# ===============================
# App / Template
# ===============================
app = FastAPI(title="Sistema de Busca + Monitoramento")
templates = Jinja2Templates(directory="app/templates")

ROOT_DIR = os.path.abspath(settings.root_dir)
DB_PATH = settings.db_path

PAGE_SIZE_DEFAULT = 20
DISK_PATH = os.getenv("DISK_PATH", ROOT_DIR)

# arquivos estáticos do sistema
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# servir arquivos (preview direto no browser)
app.mount("/arquivos", StaticFiles(directory=ROOT_DIR), name="arquivos")


# ===============================
# Utils
# ===============================
def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    return conn


def clamp_int(value: Any, default: int, min_v: int, max_v: int) -> int:
    try:
        v = int(value)
    except Exception:
        return default
    return max(min_v, min(max_v, v))


def safe_join_root(rel_path: str) -> tuple[str, str, str]:
    """
    Retorna (rel_path_normalizado, full_path, filename) com validação contra path traversal.
    """
    rel_path = unquote(rel_path or "").lstrip("/")

    # normaliza e remove caminhos estranhos
    rel_norm = os.path.normpath(rel_path).lstrip(os.sep)

    full_path = os.path.abspath(os.path.join(ROOT_DIR, rel_norm))

    # Segurança: precisa estar dentro do ROOT_DIR
    root_prefix = ROOT_DIR + os.sep
    if not (full_path.startswith(root_prefix) or full_path == ROOT_DIR):
        raise HTTPException(status_code=400, detail="Caminho inválido")

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    filename = os.path.basename(full_path)
    return rel_norm, full_path, filename


# ===============================
# Middleware: path traversal + arquivos gigantes
# ===============================
@app.middleware("http")
async def block_large_files(request: Request, call_next):
    if request.url.path.startswith("/arquivos/"):
        rel = request.url.path.replace("/arquivos/", "")
        rel_norm = os.path.normpath(rel).lstrip(os.sep)
        full = os.path.abspath(os.path.join(ROOT_DIR, rel_norm))

        root_prefix = ROOT_DIR + os.sep
        if not (full.startswith(root_prefix) or full == ROOT_DIR):
            return HTMLResponse("Caminho inválido", status_code=400)

        if os.path.exists(full) and os.path.getsize(full) > 2 * 1024 * 1024 * 1024:
            return HTMLResponse(
                "Arquivo grande demais para abrir via navegador", status_code=403
            )

    return await call_next(request)


# ===============================
# Monitoramento
# ===============================
def get_disk_usage(path: str):
    total, used, free = shutil.disk_usage(path)
    return {
        "total_tb": round(total / (1024 ** 4), 2),
        "used_tb": round(used / (1024 ** 4), 2),
        "free_tb": round(free / (1024 ** 4), 2),
        "usage_percent": round((used / total) * 100, 1),
        "path": path,
    }


def get_system_metrics():
    return {
        "cpu": psutil.cpu_percent(interval=0.2),
        "ram": psutil.virtual_memory().percent,
    }


def get_services_status():
    # exemplo: rclone
    try:
        result = subprocess.run(
            ["pgrep", "-f", "rclone"], capture_output=True, text=True
        )
        rclone_active = bool(result.stdout.strip())
    except Exception:
        rclone_active = False

    return {"rclone_active": rclone_active}


def get_recent_logs():
    log_path = os.getenv("INDEX_LOG_PATH", "index.log")
    if not os.path.exists(log_path):
        return "Sem logs ainda."
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-30:]
        return "".join(lines)
    except Exception:
        return "Não foi possível ler logs."


# ===============================
# DB helpers
# ===============================
def assert_db_root_dir():
    conn = connect(DB_PATH)
    db_root = get_meta(conn, "root_dir")
    conn.close()

    if not db_root:
        raise HTTPException(500, "Banco não inicializado. Rode: python -m app.indexer")

    if os.path.abspath(db_root) != ROOT_DIR:
        raise HTTPException(
            500, "ROOT_DIR diferente do indexado. Ajuste o .env e reindexe."
        )


def db_count_files() -> int:
    conn = db_connect()
    row = conn.execute("SELECT count(1) c FROM files_meta").fetchone()
    conn.close()
    return int(row["c"]) if row else 0


# ===============================
# Activities (DB)
# ===============================
def ensure_activities_table(conn: sqlite3.Connection):
    conn.execute("""
                 CREATE TABLE IF NOT EXISTS activities
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     action
                     TEXT
                     NOT
                     NULL,
                     filename
                     TEXT,
                     rel_path
                     TEXT,
                     created_at
                     TEXT
                     NOT
                     NULL
                 )
                 """)

    # índices úteis (não quebra se já existe)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_created_at ON activities(created_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activities_action ON activities(action)"
    )


def log_activity(action: str, filename: str | None, rel_path: str | None):
    try:
        conn = db_connect()
        conn.execute(
            """
            INSERT INTO activities (action, filename, rel_path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (action, filename, rel_path, datetime.now(tz=BR_TZ).isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ===============================
# Health / API
# ===============================
@app.get("/health")
def healthcheck():
    disk = get_disk_usage(DISK_PATH)
    try:
        conn = db_connect()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "ok"
    except Exception:
        db_status = "fail"

    overall = "ok"
    if db_status != "ok" or disk["usage_percent"] > 95:
        overall = "degraded"

    return {
        "status": overall,
        "database": db_status,
        "disk_usage_percent": disk["usage_percent"],
        "disk_path": disk["path"],
        "time": datetime.now().isoformat(),
    }


@app.get("/status", response_class=HTMLResponse)
def status_page(request: Request):
    """
    Renderiza a página HTML de status do sistema.
    """
    # Coleta os dados para exibir nos cards do topo
    data = api_status()

    # Coleta os detalhes do indexador (progresso, velocidade, etc)
    idx = get_indexer_status()

    # Conta quantos arquivos existem no banco
    total_indexed = db_count_files()

    # Pega os últimos logs gravados no arquivo index.log
    logs = get_recent_logs()

    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "data": data,
            "idx": idx,
            "total_indexed": total_indexed,
            "recent_logs": logs,
        },
    )


@app.get("/api/status")
def api_status():
    disk = get_disk_usage(DISK_PATH)
    metrics = get_system_metrics()
    services = get_services_status()

    disk_alert = disk["usage_percent"] > 90
    cpu_alert = metrics["cpu"] > 85
    ram_alert = metrics["ram"] > 85

    overall = "ok"
    if disk_alert or cpu_alert or ram_alert:
        overall = "warning"
    if disk["usage_percent"] > 95:
        overall = "critical"

    return {
        "overall_status": overall,
        "disk": disk,
        "metrics": metrics,
        "services": services,
        "alerts": {
            "disk_high": disk_alert,
            "cpu_high": cpu_alert,
            "ram_high": ram_alert,
        },
    }


@app.get("/api/index-status")
def get_indexer_status():
    conn = db_connect()
    try:
        row = conn.execute("""
                           SELECT processed,
                                  total,
                                  start_time,
                                  last_finished_time,
                                  last_duration_sec,
                                  last_new,
                                  last_updated,
                                  last_deleted,
                                  last_error
                           FROM indexer_status
                           WHERE id = 1
                           """).fetchone()
    finally:
        conn.close()

    if not row or not row["start_time"]:
        return {
            "processed": 0,
            "total": 0,
            "percent": 0,
            "speed": 0,
            "eta_sec": 0,
            "last_error": None,
        }

    processed = int(row["processed"] or 0)
    total = int(row["total"] or 0)
    start = float(row["start_time"] or time.time())

    elapsed = max(1.0, time.time() - start)
    speed = round(processed / elapsed, 1)
    percent = round((processed / total) * 100, 1) if total else 0
    eta = (
        round((total - processed) / speed, 1) if speed > 0 and total > processed else 0
    )

    return {
        "processed": processed,
        "total": total,
        "percent": percent,
        "speed": speed,
        "eta_sec": eta,
        "last_finished_time": row["last_finished_time"],
        "last_duration_sec": row["last_duration_sec"],
        "last_new": row["last_new"],
        "last_updated": row["last_updated"],
        "last_deleted": row["last_deleted"],
        "last_error": row["last_error"],
    }


@app.get("/vacuum")
def vacuum():
    conn = db_connect()
    conn.execute("VACUUM")
    conn.close()
    log_activity("vacuum", None, None)
    return {"status": "vacuum executado"}


# ===============================
# Histórico
# ===============================
def save_daily_history():
    disk = get_disk_usage(DISK_PATH)
    today = datetime.now().strftime("%Y-%m-%d")

    conn = connect(DB_PATH)
    ensure_history_table(conn)

    exists = conn.execute(
        "SELECT 1 FROM storage_history WHERE date=?", (today,)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO storage_history(date, used_tb) VALUES(?, ?)",
            (today, disk["used_tb"]),
        )
        conn.commit()

    conn.close()


@app.get("/api/history")
def history():
    conn = connect(DB_PATH)
    ensure_history_table(conn)
    rows = conn.execute(
        "SELECT date, used_tb FROM storage_history ORDER BY date"
    ).fetchall()
    conn.close()
    return {"dates": [r["date"] for r in rows], "values": [r["used_tb"] for r in rows]}


# ===============================
# Startup
# ===============================
@app.on_event("startup")
def startup():
    conn = connect(DB_PATH)

    ensure_files_schema(conn)
    ensure_history_table(conn)
    ensure_indexer_status_table(conn)
    ensure_activities_table(conn)  # 🔥 ESSENCIAL

    # índice B-Tree para busca por pasta
    conn.execute("""
                 CREATE INDEX IF NOT EXISTS idx_files_meta_rel_path
                     ON files_meta(rel_path)
                 """)

    conn.commit()
    conn.close()

    save_daily_history()


# ===============================
# Páginas
# ===============================


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "results": [],
            "last_query": "",
            "error": "",
            "meta": {
                "total_indexed": db_count_files(),
                "query_ms": None,
                "total_matches": 0,
                "page": 1,
                "total_pages": 0,
                "pages_to_show": [],  # Mantém vazio pois não há busca
                "page_size": PAGE_SIZE_DEFAULT,
                "order": "recent",
            },
        },
    )


# ===============================
# Busca (FTS + fallback LIKE)
# ===============================

@app.get("/search")
async def search_get(request: Request):
    """Redireciona para a home se tentarem acessar /search via URL direta"""
    return RedirectResponse(url="/")


@app.post("/search", response_class=HTMLResponse)
async def search(
        request: Request,
        query: str = Form(...),
        page: int = Form(1),
        page_size: int = Form(PAGE_SIZE_DEFAULT),
        order: str = Form("recent"),
        search_type: str = Form("all"),
):
    assert_db_root_dir()

    q_raw = (query or "").strip()
    q = q_raw
    q_lower = q_raw.lower()

    COMMON_EXTS = {
        "txt",
        "pdf",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "gif",
        "svg",
        "mp4",
        "webm",
        "mov",
        "mkv",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "zip",
        "rar",
        "7z",
        "json",
        "csv",
        "log",
        "py",
        "js",
        "ts",
        "html",
        "css",
        "php",
        "java",
        "c",
        "cpp",
        "h",
    }
    ext_query = None
    if q_lower.startswith(".") and len(q_lower) >= 2:
        ext_query = q_lower[1:]
    elif q_lower in COMMON_EXTS:
        ext_query = q_lower

    total_indexed = db_count_files()
    page_size = clamp_int(page_size, PAGE_SIZE_DEFAULT, 5, 100)
    page = clamp_int(page, 1, 1, 100000)

    if (
            (not (q_lower.startswith(".") and len(q_lower) >= 2))
            and (not ext_query)
            and len(q) < 2
    ):
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
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
            },
        )

    log_activity("search", None, q)
    order_map = {
        "name_asc": "m.filename COLLATE NOCASE ASC",
        "name_desc": "m.filename COLLATE NOCASE DESC",
        "recent": "m.modified_at DESC",
        "oldest": "m.modified_at ASC",
        "size_desc": "m.size_bytes DESC, m.filename ASC",  # Adicionado critério de desempate
        "type": "m.ext ASC, m.filename ASC"
    }

    # Pegamos o valor com fallback seguro
    order_sql = order_map.get(order, "m.modified_at DESC")
    offset = (page - 1) * page_size
    t0 = time.perf_counter()

    conn = db_connect()
    cur = conn.cursor()
    like_any = f"%{q}%"
    q_path = "%" + "%".join(q.split()) + "%"

    try:
        rows = []
        total_matches = 0

        # --- LÓGICA DE BUSCA (SQL) ---
        if ext_query:
            total_matches = cur.execute(
                "SELECT COUNT(*) c FROM files_meta WHERE REPLACE(LOWER(ext), '.', '') = ?",
                (ext_query,),
            ).fetchone()["c"]
            rows = cur.execute(
                f"SELECT filename, rel_path, ext, ROUND(size_bytes/1024.0/1024.0, 2) AS size_mb, created_at, modified_at FROM files_meta WHERE REPLACE(LOWER(ext), '.', '') = ? ORDER BY {order_sql.replace('m.', '')} LIMIT ? OFFSET ?",
                (ext_query, page_size, offset),
            ).fetchall()
        else:
            # Fallback para FTS ou LIKE (mantendo sua lógica original)
            tokens = "".join([ch if ch.isalnum() else " " for ch in q_lower]).split()
            fts_term = " ".join([f"{t}*" for t in tokens]) if tokens else f"{q}*"

            # Tenta FTS primeiro
            fts_count = cur.execute(
                "SELECT COUNT(*) c FROM files WHERE files MATCH ?", (fts_term,)
            ).fetchone()["c"]
            if fts_count > 0:
                total_matches = fts_count
                rows = cur.execute(
                    f"SELECT m.filename, m.rel_path, m.ext, ROUND(m.size_bytes/1024.0/1024.0, 2) AS size_mb, m.created_at, m.modified_at FROM files JOIN files_meta m ON m.id = files.rowid WHERE files MATCH ? ORDER BY {order_sql} LIMIT ? OFFSET ?",
                    (fts_term, page_size, offset),
                ).fetchall()
            else:
                # LIKE
                where_sql = "filename LIKE ? OR rel_path LIKE ?"
                total_matches = cur.execute(
                    f"SELECT COUNT(*) c FROM files_meta WHERE {where_sql}",
                    (like_any, q_path),
                ).fetchone()["c"]
                rows = cur.execute(
                    f"SELECT filename, rel_path, ext, ROUND(size_bytes/1024.0/1024.0, 2) AS size_mb, created_at, modified_at FROM files_meta WHERE {where_sql} ORDER BY {order_sql.replace('m.', '')} LIMIT ? OFFSET ?",
                    (like_any, q_path, page_size, offset),
                ).fetchall()

    except sqlite3.OperationalError:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
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
            },
        )
    finally:
        conn.close()

    # --- CÁLCULO DA PAGINAÇÃO DINÂMICA ---
    total_pages = ceil(total_matches / page_size) if total_matches > 0 else 0
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1

    # Define quantos botões mostrar ao redor da página atual
    window = 2
    start_page = max(1, page - window)
    end_page = min(total_pages, page + window)

    # Se estiver no início, garante que mostra pelo menos até a página 5
    if page <= 3:
        end_page = min(total_pages, 5)

    # Se estiver no fim, garante que mostra as últimas 5
    if page > total_pages - 3:
        start_page = max(1, total_pages - 4)

    pages_to_show = list(range(start_page, end_page + 1))

    # Detecta sistema do usuário
    sistema = detectar_sistema(request.headers.get("user-agent", ""))

    results = []

    for r in rows:
        caminho_linux = os.path.join(settings.root_dir, r["rel_path"])

        caminho_publico = converter.gerar_caminho_publico(
            caminho_linux,
            sistema
        )

        results.append({
            "filename": r["filename"],
            "rel_path": r["rel_path"],
            "ext": r["ext"] or "",
            "size_mb": r["size_mb"],
            "created_at": r["created_at"],
            "modified_at": r["modified_at"],
            "preview_link": f"/arquivos/{quote(r['rel_path'])}",
            "network_path": caminho_publico,
        })

    query_ms = round((time.perf_counter() - t0) * 1000, 2)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
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
                "order": order,
            },
        },
    )


@app.get("/api/full-status")
def full_status():
    return {
        "disk": get_disk_usage(DISK_PATH),
        "metrics": get_system_metrics(),
        "services": get_services_status(),
        "indexer": get_indexer_status(),
        "time": datetime.now().isoformat(),
    }


# ===============================
# Activities API
# ===============================
@app.get("/api/activities")
def recent_activities(limit: int = 10):
    limit = clamp_int(limit, 10, 1, 100)

    conn = db_connect()
    rows = conn.execute(
        """
                        SELECT action, filename, rel_path, created_at
                        FROM activities
                        ORDER BY created_at DESC
                            LIMIT ?
                        """,
        (limit,),
    ).fetchall()
    conn.close()

    return [
        {
            "action": r["action"],
            "filename": r["filename"],
            "rel_path": r["rel_path"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@app.post("/api/activities/clear")
def clear_activities():
    conn = db_connect()
    conn.execute("DELETE FROM activities")
    conn.commit()
    conn.close()
    log_activity("clear_activities", None, None)
    return {"ok": True}


# ===============================
# Preview & Download (com log)
# ===============================
@app.get("/preview")
def preview_file(path: str):
    # ✅ loga preview e redireciona para /arquivos/...
    rel_norm, full_path, filename = safe_join_root(path)

    log_activity(action="preview", filename=filename, rel_path=rel_norm)

    return RedirectResponse(url=f"/arquivos/{quote(rel_norm)}")


@app.get("/download")
def download_file(path: str):
    # ✅ faz download real + log
    rel_norm, full_path, filename = safe_join_root(path)

    log_activity(action="download", filename=filename, rel_path=rel_norm)

    return FileResponse(
        path=full_path, filename=filename, media_type="application/octet-stream"
    )
