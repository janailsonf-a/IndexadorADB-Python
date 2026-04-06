from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
import mimetypes

from app.core.constants import ROOT_DIR

router = APIRouter()


@router.get("/preview")
def preview_file(path: str = Query(...)):
    root = Path(ROOT_DIR).resolve()
    file_path = (root / path).resolve()

    if not str(file_path).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Caminho inválido")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    media_type, _ = mimetypes.guess_type(str(file_path))
    media_type = media_type or "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
    )