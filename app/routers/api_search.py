from fastapi import APIRouter, Query, Request

from app.core.constants import PAGE_SIZE_DEFAULT
from app.services.search_service import SearchService

router = APIRouter(prefix="/api", tags=["api-search"])
search_service = SearchService()


@router.get("/search")
async def api_search(
    request: Request,
    query: str = Query(""),
    page: int = Query(1),
    page_size: int = Query(PAGE_SIZE_DEFAULT),
    order: str = Query("recent"),
):
    payload = search_service.search(request, query, page, page_size, order)
    return payload