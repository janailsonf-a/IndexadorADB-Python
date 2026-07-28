from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
import mimetypes

from app.auth import get_current_user
from app.core.constants import (
    MAX_DOWNLOAD_SIZE,
    MAX_PREVIEW_SIZE,
    SAFE_INLINE_EXTENSIONS,
    THUMB_CACHE_DIR,
)
from app.core.logger import logger
from app.services.activity_service import ActivityService
from app.services.file_service import FileService
from app.services.thumbnail_service import ThumbnailService

router = APIRouter()
file_service = FileService()
thumbnail_service = ThumbnailService(THUMB_CACHE_DIR)


def guess_media_type(full_path, filename: str) -> str:
    media_type, _ = mimetypes.guess_type(str(full_path))

    if not media_type:
        ext = filename.lower().split(".")[-1] if "." in filename else ""

        fallback_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "gif": "image/gif",
            "svg": "image/svg+xml",
            "bmp": "image/bmp",
            "avif": "image/avif",
            "pdf": "application/pdf",
            "txt": "text/plain; charset=utf-8",
            "log": "text/plain; charset=utf-8",
            "json": "application/json",
            "csv": "text/csv; charset=utf-8",
            "html": "text/html; charset=utf-8",
            "css": "text/css; charset=utf-8",
            "xml": "application/xml",
            "mp4": "video/mp4",
            "webm": "video/webm",
        }

        media_type = fallback_map.get(ext, "application/octet-stream")

    return media_type


@router.get("/api/thumbnail")
def video_thumbnail(
    path: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Miniatura (1º quadro) de um vídeo, como JPEG pequeno e cacheado.
    Não passa pelo limite de MAX_PREVIEW_SIZE de propósito: o ffmpeg lê o
    arquivo local e só o JPEG gerado vai pra rede, então o tamanho do vídeo
    original é irrelevante pro cliente.
    """
    rel_norm, full_path, filename = file_service.safe_join_root(path)

    if not thumbnail_service.is_video(filename):
        raise HTTPException(
            status_code=400,
            detail="Miniatura disponível apenas para vídeos",
        )

    thumb = thumbnail_service.get_or_create(rel_norm, full_path)

    if thumb is None:
        raise HTTPException(
            status_code=422,
            detail="Não foi possível gerar a miniatura deste vídeo",
        )

    return FileResponse(
        path=thumb,
        media_type="image/jpeg",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=86400",
        },
    )


@router.get("/preview")
def preview_file(
    path: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    rel_norm, full_path, filename = file_service.safe_join_root(path)
    file_service.ensure_allowed_extension(filename, SAFE_INLINE_EXTENSIONS, "preview")
    file_service.ensure_file_size(full_path, MAX_PREVIEW_SIZE, "preview")
    ActivityService.log("preview", filename, rel_norm, current_user=current_user)

    media_type = guess_media_type(full_path, filename)

    logger.info("PREVIEW file=%s mime=%s", full_path, media_type)

    return FileResponse(
        path=full_path,
        media_type=media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/download")
def download_file(
    path: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    rel_norm, full_path, filename = file_service.safe_join_root(path)
    file_service.ensure_file_size(full_path, MAX_DOWNLOAD_SIZE, "download")
    ActivityService.log("download", filename, rel_norm, current_user=current_user)

    media_type = guess_media_type(full_path, filename)

    logger.info("DOWNLOAD file=%s mime=%s", full_path, media_type)

    return FileResponse(
        path=full_path,
        filename=filename,
        media_type=media_type,
        content_disposition_type="attachment",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/files/{file_path:path}")
def serve_file(
    file_path: str,
    disposition: str = Query("inline"),
    current_user: dict = Depends(get_current_user),
):
    rel_norm, full_path, filename = file_service.safe_join_root(file_path)
    file_service.ensure_allowed_extension(filename, SAFE_INLINE_EXTENSIONS, "visualização")
    file_service.ensure_file_size(full_path, MAX_PREVIEW_SIZE, "visualização")
    ActivityService.log("serve_file", filename, rel_norm, current_user=current_user)

    media_type = guess_media_type(full_path, filename)

    logger.info("SERVE file=%s mime=%s disposition=%s", full_path, media_type, disposition)

    if disposition == "attachment":
        return FileResponse(
            path=full_path,
            filename=filename,
            media_type=media_type,
            content_disposition_type="attachment",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )

    return FileResponse(
        path=full_path,
        media_type=media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )