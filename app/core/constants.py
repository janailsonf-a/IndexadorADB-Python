from pathlib import Path
from zoneinfo import ZoneInfo
import os

from app.config import settings

settings.validate()

BR_TZ = ZoneInfo("America/Sao_Paulo")
ROOT_DIR = Path(settings.root_dir).expanduser().resolve()
DB_PATH = settings.db_path

PAGE_SIZE_DEFAULT = 20
DISK_PATH = os.getenv("DISK_PATH", str(ROOT_DIR))

# Cache de miniaturas de vídeo — fica ao lado do banco (mesmo volume persistente,
# então sobrevive a rebuild do container)
THUMB_CACHE_DIR = Path(DB_PATH).expanduser().resolve().parent / "thumbs"

MAX_PREVIEW_SIZE = settings.max_preview_size_mb * 1024 * 1024
MAX_DOWNLOAD_SIZE = settings.max_download_size_mb * 1024 * 1024

# Vídeo tem limite próprio, muito maior: o acervo é ~83% vídeo e boa parte
# passa de 100MB, então o limite de preview (50MB, pensado pra imagem/PDF que
# o navegador baixa inteiro) barraria quase todo o acervo no player. Servir
# vídeo é seguro porque o FileResponse responde 206/Range — o navegador puxa
# só os pedaços que está assistindo, não o arquivo todo.
MAX_VIDEO_PREVIEW_SIZE = int(os.getenv("MAX_VIDEO_PREVIEW_SIZE_MB", "4096")) * 1024 * 1024

SAFE_TEXT_EXTENSIONS = {
    "txt", "log", "json", "csv", "py", "js", "html", "css", "md", "xml", "yml", "yaml"
}

SAFE_INLINE_EXTENSIONS = SAFE_TEXT_EXTENSIONS | {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "gif",
    "svg",
    "bmp",
    "avif",
    "pdf",
    "mp4",
    "webm",
}