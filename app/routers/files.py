from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, RedirectResponse

from app.core.constants import MAX_DOWNLOAD_SIZE, MAX_PREVIEW_SIZE, SAFE_INLINE_EXTENSIONS
from app.services.activity_service import ActivityService
from app.services.file_service import FileService

router = APIRouter()
file_service = FileService()


@router.get("/preview")
def preview_file(path: str):
    rel_norm, full_path, filename = file_service.safe_join_root(path)
    file_service.ensure_allowed_extension(filename, SAFE_INLINE_EXTENSIONS, "preview")
    file_service.ensure_file_size(full_path, MAX_PREVIEW_SIZE, "preview")
    ActivityService.log("preview", filename, rel_norm)
    return RedirectResponse(url=f"/files/{quote(rel_norm)}?disposition=inline")


@router.get("/download")
def download_file(path: str):
    rel_norm, full_path, filename = file_service.safe_join_root(path)
    file_service.ensure_file_size(full_path, MAX_DOWNLOAD_SIZE, "download")
    ActivityService.log("download", filename, rel_norm)
    return FileResponse(path=full_path, filename=filename, media_type="application/octet-stream")


@router.get("/files/{file_path:path}")
def serve_file(file_path: str, disposition: str = Query("inline")):
    rel_norm, full_path, filename = file_service.safe_join_root(file_path)
    file_service.ensure_allowed_extension(filename, SAFE_INLINE_EXTENSIONS, "visualização")
    file_service.ensure_file_size(full_path, MAX_PREVIEW_SIZE, "visualização")
    ActivityService.log("serve_file", filename, rel_norm)

    headers = {"X-Content-Type-Options": "nosniff"}

    if disposition == "attachment":
        return FileResponse(
            path=full_path,
            filename=filename,
            media_type="application/octet-stream",
            headers=headers,
        )

    return FileResponse(path=full_path, filename=filename, headers=headers)