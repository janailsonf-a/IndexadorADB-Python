from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    root_dir: str | None = os.getenv("ROOT_DIR")
    db_path: str | None = os.getenv("DB_PATH")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "9001"))
    max_results: int = int(os.getenv("MAX_RESULTS", "50"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_path: str = os.getenv("LOG_PATH", "logs/app.log")
    max_preview_size_mb: int = int(os.getenv("MAX_PREVIEW_SIZE_MB", "50"))
    max_download_size_mb: int = int(os.getenv("MAX_DOWNLOAD_SIZE_MB", "2048"))

    def validate(self) -> None:
        errors: list[str] = []

        if not self.root_dir:
            errors.append("ROOT_DIR não foi definido no .env")
        if not self.db_path:
            errors.append("DB_PATH não foi definido no .env")

        if errors:
            raise RuntimeError(" | ".join(errors))

        root = Path(self.root_dir).expanduser().resolve()
        db_parent = Path(self.db_path).expanduser().resolve().parent

        if not root.exists():
            errors.append(f"ROOT_DIR não existe: {root}")
        elif not root.is_dir():
            errors.append(f"ROOT_DIR não é uma pasta: {root}")
        elif not os.access(root, os.R_OK):
            errors.append(f"Sem permissão de leitura em ROOT_DIR: {root}")

        if not db_parent.exists():
            errors.append(f"Pasta do DB_PATH não existe: {db_parent}")

        if self.port <= 0 or self.port > 65535:
            errors.append(f"PORT inválida: {self.port}")

        if errors:
            raise RuntimeError(" | ".join(errors))


settings = Settings()