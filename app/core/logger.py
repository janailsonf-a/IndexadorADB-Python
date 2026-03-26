import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

from app.config import settings


def configure_logging() -> logging.Logger:
    os.makedirs(Path(settings.log_path).parent, exist_ok=True)

    logger = logging.getLogger("indexador")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )

        file_handler = RotatingFileHandler(
            settings.log_path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger


logger = configure_logging()