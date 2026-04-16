from fastapi import APIRouter, Depends, HTTPException, Query
from sqlite3 import Connection

from app.auth import get_current_user, require_admin
from app.db import get_db
from app.schemas.metadata import FileMetadataResponse, FileMetadataUpdate
from app.services.metadata_service import (
    get_all_tags,
    get_file_metadata,
    update_file_metadata,
)

router = APIRouter(prefix="/api/files", tags=["metadata"])


@router.get("/{file_id}/metadata", response_model=FileMetadataResponse)
def read_file_metadata(
    file_id: int,
    conn: Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    data = get_file_metadata(conn, file_id)
    if not data:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return data


@router.put("/{file_id}/metadata", response_model=FileMetadataResponse)
def save_file_metadata(
    file_id: int,
    payload: FileMetadataUpdate,
    conn: Connection = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    updated = update_file_metadata(conn, file_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return updated


@router.get("/tags/suggestions")
def tags_suggestions(
    limit: int = Query(default=50, ge=1, le=200),
    conn: Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return {"tags": get_all_tags(conn, limit=limit)}