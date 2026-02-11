from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    root_dir: str = os.getenv("ROOT_DIR", "/home/janailson/arquivos_teste")
    db_path = "/var/lib/indexador/file_index.db"
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    max_results: int = int(os.getenv("MAX_RESULTS", "50"))

settings = Settings()