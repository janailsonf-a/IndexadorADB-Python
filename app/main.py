from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router



from app.core.constants import DB_PATH, ROOT_DIR
from app.core.logger import logger
from app.db import (
    connect,
    ensure_files_schema,
    ensure_metadata_columns,
    ensure_content_hash_column,
    ensure_history_table,
    ensure_indexer_status_table,
)
from app.repositories.activities_repository import ensure_activities_table
from app.services.history_service import HistoryService
from app.routers.web import router as web_router
from app.routers.files import router as files_router
from app.routers.status import router as status_router
from app.routers.history import router as history_router
from app.routers.activities import router as activities_router
from app.routers.api_search import router as api_search_router
from app.routers.metadata import router as metadata_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando aplicação com ROOT_DIR=%s DB_PATH=%s", ROOT_DIR, DB_PATH)

    conn = connect(DB_PATH)
    try:
        ensure_files_schema(conn)
        ensure_metadata_columns(conn)
        ensure_content_hash_column(conn)
        ensure_history_table(conn)
        ensure_indexer_status_table(conn)
        ensure_activities_table(conn)
        conn.commit()
    finally:
        conn.close()

    HistoryService.save_daily_history()
    yield


app = FastAPI(
    title="Sistema de Busca + Monitoramento",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://192.168.0.162:9101",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/arquivos", StaticFiles(directory=ROOT_DIR), name="arquivos")

app.include_router(web_router)
app.include_router(files_router)
app.include_router(status_router)
app.include_router(history_router)
app.include_router(activities_router)
app.include_router(api_search_router)
app.include_router(metadata_router)
app.include_router(auth_router)
app.include_router(users_router)


@app.exception_handler(RuntimeError)
async def runtime_error_handler(_: Request, exc: RuntimeError):
    logger.exception("Erro de runtime: %s", exc)
    return HTMLResponse(str(exc), status_code=500)