from pydantic import BaseModel, Field
from typing import List, Optional


class SearchResultItem(BaseModel):
    id: str
    filename: str
    rel_path: str
    full_path: str
    ext: str = ""
    area: str = "Geral"
    size_mb: Optional[float] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    preview_link: Optional[str] = None
    download_link: Optional[str] = None

    title: Optional[str] = None
    description: Optional[str] = None
    campaign: Optional[str] = None
    status: Optional[str] = None
    is_official: bool = False
    tags: List[str] = Field(default_factory=list)


class SearchMeta(BaseModel):
    total_indexed: int = 0
    total_matches: int = 0
    query_ms: Optional[float] = None
    page: int = 1
    total_pages: int = 0
    page_size: int = 20
    order: str = "recent"
    pages_to_show: List[int] = Field(default_factory=list)


class SearchResponse(BaseModel):
    results: List[SearchResultItem] = Field(default_factory=list)
    meta: SearchMeta
    error: str = ""
    last_query: str = ""