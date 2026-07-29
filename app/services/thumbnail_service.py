"""
Geração de miniatura (thumbnail) de vídeo via ffmpeg, com cache em disco.

Por que no backend em vez de deixar o navegador renderizar <video>:
os vídeos do acervo real chegam a centenas de MB (277MB, 615MB...), acima do
MAX_PREVIEW_SIZE, e mesmo que passassem o navegador teria que baixar dezenas
de MB por card só pra mostrar um quadro. Aqui o ffmpeg lê o arquivo local e
devolve um JPEG de ~20KB, cacheado — o cliente baixa só isso.
"""

import hashlib
import subprocess
import threading
from pathlib import Path
from typing import Optional

from app.core.logger import logger

VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "mkv", "avi", "wmv", "m4v", "mpg", "mpeg"}

THUMB_WIDTH = 400
FFMPEG_TIMEOUT_SEC = 30

# O acervo é ~83% vídeo, então uma página de 50 cards dispara dezenas de
# pedidos de miniatura de uma vez. Sem limite, seriam dezenas de ffmpeg
# simultâneos lendo arquivos de centenas de MB — o servidor não aguenta.
# Miniatura em fila é aceitável; servidor no chão não.
MAX_CONCURRENT_FFMPEG = 3
_ffmpeg_slots = threading.Semaphore(MAX_CONCURRENT_FFMPEG)
# Espera na fila: se estourar, é melhor devolver erro (o card cai no ícone)
# do que segurar a conexão indefinidamente.
FFMPEG_QUEUE_TIMEOUT_SEC = 25


class ThumbnailService:
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)

    @staticmethod
    def is_video(filename: str) -> bool:
        ext = Path(filename).suffix.lower().lstrip(".")
        return ext in VIDEO_EXTENSIONS

    def _cache_path(self, rel_path: str) -> Path:
        key = hashlib.md5(rel_path.encode()).hexdigest()
        return self.cache_dir / f"{key}.jpg"

    def _is_cache_fresh(self, cache_path: Path, source: Path) -> bool:
        """Cache válido se existe, não está vazio e é mais novo que o vídeo."""
        if not cache_path.exists() or cache_path.stat().st_size == 0:
            return False
        return cache_path.stat().st_mtime >= source.stat().st_mtime

    def _run_ffmpeg(self, source: Path, dest: Path, seek_sec: float) -> bool:
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-loglevel", "error",
            "-ss", str(seek_sec),
            "-i", str(source),
            "-frames:v", "1",
            "-vf", f"scale={THUMB_WIDTH}:-2",
            "-q:v", "5",
            "-y",
            str(dest),
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                timeout=FFMPEG_TIMEOUT_SEC,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            logger.error("ffmpeg não encontrado no PATH — thumbnail de vídeo indisponível")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg timeout gerando thumbnail de %s", source)
            return False
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode(errors="replace").strip()
            logger.warning("ffmpeg falhou em %s (seek=%s): %s", source, seek_sec, stderr[:300])
            return False

        return dest.exists() and dest.stat().st_size > 0

    def get_or_create(self, rel_path: str, source: Path) -> Optional[Path]:
        """
        Devolve o caminho do JPEG de miniatura, gerando se necessário.
        None se não foi possível gerar (ffmpeg ausente, vídeo corrompido etc).
        """
        cache_path = self._cache_path(rel_path)

        if self._is_cache_fresh(cache_path, source):
            return cache_path

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if not _ffmpeg_slots.acquire(timeout=FFMPEG_QUEUE_TIMEOUT_SEC):
            logger.warning("fila de ffmpeg cheia, desistindo da miniatura de %s", source)
            return None

        try:
            # outro request pode ter gerado enquanto esperávamos na fila
            if self._is_cache_fresh(cache_path, source):
                return cache_path

            # 1s pra frente evita o quadro preto/fade-in comum no início; se o
            # vídeo for mais curto que isso, o seek falha e caímos pro quadro 0.
            for seek in (1.0, 0.0):
                if self._run_ffmpeg(source, cache_path, seek):
                    return cache_path
        finally:
            _ffmpeg_slots.release()

        return None
