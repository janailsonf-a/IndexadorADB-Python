from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    root_dir: str = os.getenv("ROOT_DIR")
    db_path: str = os.getenv("DB_PATH")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "9001"))
    max_results: int = int(os.getenv("MAX_RESULTS", "50"))


settings = Settings()
