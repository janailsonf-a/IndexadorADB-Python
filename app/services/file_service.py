import os
from pathlib import Path
from urllib.parse import unquote

from fastapi import HTTPException

from app.core.constants import ROOT_DIR


class FileService:
    @staticmethod
    def safe_join_root(rel_path: str) -> tuple[str, Path, str]:
        rel_path = unquote(rel_path or "").lstrip("/")
        rel_norm = os.path.normpath(rel_path).lstrip(os.sep)
        full_path = (ROOT_DIR / rel_norm).resolve()

        if not str(full_path).startswith(str(ROOT_DIR)):
            raise HTTPException(status_code=400, detail="Caminho inválido")
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Arquivo não encontrado")
        if full_path.is_dir():
            raise HTTPException(status_code=400, detail="Pastas não podem ser abertas")

        return rel_norm, full_path, full_path.name

    @staticmethod
    def ensure_allowed_extension(filename: str, allowed_exts: set[str], action: str) -> str:
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in allowed_exts:
            raise HTTPException(
                status_code=403,
                detail=f"Tipo de arquivo não permitido para {action}: .{ext or 'sem_ext'}",
            )
        return ext

    @staticmethod
    def ensure_file_size(path: Path, max_size: int, action: str) -> None:
        size = path.stat().st_size
        if size > max_size:
            raise HTTPException(
                status_code=403,
                detail=f"Arquivo grande demais para {action}",
            )