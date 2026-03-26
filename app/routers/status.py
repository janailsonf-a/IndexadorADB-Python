from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.repositories.db_connection import db_connect
from app.repositories.status_repository import get_indexer_status_data
from app.services.activity_service import ActivityService
from app.services.status_service import StatusService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/health")
def healthcheck():
    return StatusService.healthcheck()


@router.get("/status", response_class=HTMLResponse)
def status_page(request: Request):
    return templates.TemplateResponse(
        request,
        "status.html",
        {
            "request": request,
            **StatusService.status_page_context(),
        },
    )


@router.get("/api/status")
def api_status():
    return StatusService.api_status()


@router.get("/api/index-status")
def get_indexer_status():
    return get_indexer_status_data()


@router.get("/api/full-status")
def full_status():
    return StatusService.full_status()


@router.get("/vacuum")
def vacuum():
    conn = db_connect()
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()

    ActivityService.log("vacuum", None, None)
    return {"status": "vacuum executado"}