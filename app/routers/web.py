from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.constants import PAGE_SIZE_DEFAULT
from app.repositories.status_repository import db_count_files
from app.services.search_service import SearchService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
search_service = SearchService()


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    query: str = Query(""),
    page: int = Query(1),
    page_size: int = Query(PAGE_SIZE_DEFAULT),
    order: str = Query("recent"),
):
    if (query or "").strip():
        payload = search_service.search(request, query, page, page_size, order)
        return templates.TemplateResponse(
            request,
            "index.html",
            {"request": request, **payload},
        )

    return templates.TemplateResponse(
        request,
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
                "pages_to_show": [],
                "page_size": PAGE_SIZE_DEFAULT,
                "order": "recent",
            },
        },
    )


@router.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    query: str = Query(...),
    page: int = Query(1),
    page_size: int = Query(PAGE_SIZE_DEFAULT),
    order: str = Query("recent"),
):
    payload = search_service.search(request, query, page, page_size, order)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request, **payload},
    )