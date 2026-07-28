from fastapi import APIRouter, Depends, Query, Request

from app.auth import get_current_user
from app.core.constants import PAGE_SIZE_DEFAULT
from app.schemas.search import SearchResponse, DuplicatesResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/api", tags=["api-search"])
search_service = SearchService()


@router.get("/duplicates", response_model=DuplicatesResponse)
async def api_duplicates(request: Request, limit_groups: int = Query(default=200, ge=1, le=1000)):
    return search_service.duplicates(request=request, limit_groups=limit_groups)


@router.get("/search", response_model=SearchResponse)
async def api_search(
    request: Request,
    query: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=PAGE_SIZE_DEFAULT, ge=5, le=100),
    order: str = Query(default="recent"),
    ext: str = Query(default=""),
    area: str = Query(default=""),
    current_user: dict = Depends(get_current_user),
):
    return search_service.search_api(
        request=request,
        query=query,
        page=page,
        page_size=page_size,
        order=order,
        ext=ext,
        area=area,
        current_user=current_user,
    )