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

MAX_PREVIEW_SIZE = settings.max_preview_size_mb * 1024 * 1024
MAX_DOWNLOAD_SIZE = settings.max_download_size_mb * 1024 * 1024

SAFE_TEXT_EXTENSIONS = {
    "txt", "log", "json", "csv", "py", "js", "html", "css", "md", "xml", "yml", "yaml"
}

SAFE_INLINE_EXTENSIONS = SAFE_TEXT_EXTENSIONS | {
    "jpg", "jpeg", "png", "webp", "gif", "svg", "pdf", "mp4", "webm"
}