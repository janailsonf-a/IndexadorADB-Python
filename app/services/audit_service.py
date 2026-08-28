"""
Auditoria tecnica de um arquivo: junta o que esta no indice, o que o sistema
de arquivos diz agora, e o que o ffprobe consegue ler do conteudo.

Serve pra decidir com seguranca em telas como a de duplicatas — saber de qual
servidor o arquivo vem, a resolucao real, e se o que esta no indice ainda
corresponde ao arquivo em disco.
"""

import json
import mimetypes
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.constants import ROOT_DIR
from app.core.logger import logger

FFPROBE_TIMEOUT_SEC = 20

# Subarvores que vem de outra origem que nao o disco local. A chave e o prefixo
# do rel_path (o ponto de montagem dentro do ROOT_DIR).
ORIGENS = {
    "_winmkt": {
        "rotulo": "Servidor de mídias (.78)",
        "detalhe": "//192.168.0.78/revisao/DAS MIDIAS EXTERNAS — montagem CIFS, somente leitura",
        "somente_leitura": True,
    },
}
ORIGEM_LOCAL = {
    "rotulo": "Disco local do servidor",
    "detalhe": "/mnt/share no host (acervo principal)",
    "somente_leitura": False,
}


def _origem(rel_path: str) -> dict:
    norm = (rel_path or "").replace("\\", "/").lstrip("/")
    for prefixo, info in ORIGENS.items():
        if norm == prefixo or norm.startswith(prefixo + "/"):
            return {**info, "prefixo": prefixo}
    return {**ORIGEM_LOCAL, "prefixo": ""}


def _humano(n: Optional[int]) -> str:
    if not n:
        return "0 B"
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unidade == "TB":
            return f"{n:.0f} {unidade}" if unidade == "B" else f"{n:.1f} {unidade}"
        n /= 1024.0
    return f"{n:.1f} TB"


def _iso(ts: Optional[float]) -> Optional[str]:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def _ffprobe(caminho: Path) -> dict:
    """Le dimensoes/duracao/codec do conteudo. So headers, nao le o arquivo todo."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,bit_rate,format_long_name,nb_streams",
        "-show_entries", "stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(caminho),
    ]
    try:
        out = subprocess.run(
            cmd, capture_output=True, timeout=FFPROBE_TIMEOUT_SEC, check=True
        ).stdout
        return json.loads(out or b"{}")
    except FileNotFoundError:
        logger.warning("ffprobe nao encontrado — auditoria sem dados tecnicos")
    except subprocess.TimeoutExpired:
        logger.warning("ffprobe estourou o tempo em %s", caminho)
    except subprocess.CalledProcessError:
        pass  # formato que o ffprobe nao le (doc, zip...) — normal
    except json.JSONDecodeError:
        pass
    return {}


def _mdc(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def auditar(row) -> dict:
    """`row` e uma linha de files_meta. Devolve o dossie tecnico do arquivo."""
    rel_path = row["rel_path"]
    full = (ROOT_DIR / rel_path)
    origem = _origem(rel_path)

    indice = {
        "id": row["id"],
        "nome": row["filename"],
        "caminho_relativo": rel_path,
        "caminho_absoluto": str(full),
        "extensao": (row["ext"] or "").lower(),
        "tamanho_bytes": row["size_bytes"],
        "tamanho_humano": _humano(row["size_bytes"]),
        "criado_em": row["created_at"],
        "modificado_em": row["modified_at"],
        "hash_conteudo": row["content_hash"] or None,
        "hash_caminho": row["path_hash"],
    }
    # content_hash vazio e intencional (subarvore de rede), diferente de nunca calculado
    if row["content_hash"] == "":
        indice["hash_conteudo"] = None
        indice["hash_observacao"] = "não calculado — arquivo em montagem de rede"

    disco = {"existe": False}
    try:
        st = full.stat()
        disco = {
            "existe": True,
            "tamanho_bytes": st.st_size,
            "tamanho_humano": _humano(st.st_size),
            "modificado_em": _iso(st.st_mtime),
            "acessado_em": _iso(st.st_atime),
            "permissoes": oct(st.st_mode & 0o777),
            "inode": st.st_ino,
            # divergencia entre indice e disco significa indice desatualizado
            "difere_do_indice": st.st_size != (row["size_bytes"] or 0),
        }
    except OSError as exc:
        disco["erro"] = str(exc)

    tecnico = {}
    if disco.get("existe"):
        probe = _ffprobe(full)
        fmt = probe.get("format", {}) or {}
        streams = probe.get("streams", []) or []

        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if fmt.get("format_long_name"):
            tecnico["formato"] = fmt["format_long_name"]
        if fmt.get("duration"):
            try:
                seg = float(fmt["duration"])
                tecnico["duracao_seg"] = round(seg, 2)
                tecnico["duracao"] = f"{int(seg // 60)}:{int(seg % 60):02d}"
            except ValueError:
                pass
        if fmt.get("bit_rate"):
            try:
                tecnico["bitrate"] = f"{int(fmt['bit_rate']) / 1_000_000:.2f} Mbps"
            except ValueError:
                pass

        if video:
            w, h = video.get("width"), video.get("height")
            if w and h:
                tecnico["largura"] = w
                tecnico["altura"] = h
                tecnico["dimensoes"] = f"{w} × {h}"
                tecnico["megapixels"] = round(w * h / 1_000_000, 1)
                d = _mdc(w, h) or 1
                tecnico["proporcao"] = f"{w // d}:{h // d}"
            if video.get("codec_name"):
                tecnico["codec_video"] = video["codec_name"]
            fr = video.get("r_frame_rate") or ""
            if "/" in fr:
                num, den = fr.split("/")
                try:
                    if float(den):
                        tecnico["fps"] = round(float(num) / float(den), 2)
                except ValueError:
                    pass
        if audio:
            tecnico["codec_audio"] = audio.get("codec_name")
            if audio.get("sample_rate"):
                tecnico["taxa_amostragem"] = f"{int(audio['sample_rate']) / 1000:.1f} kHz"
            if audio.get("channels"):
                tecnico["canais"] = audio["channels"]

    mime, _ = mimetypes.guess_type(str(full))

    # imagem parada: o ffprobe inventa duracao/fps/bitrate ("image2 sequence",
    # 0.04s, 25fps) porque trata como video de 1 quadro. Nao mostrar isso.
    if (mime or "").startswith("image/"):
        for chave in ("duracao", "duracao_seg", "fps", "bitrate", "formato", "codec_audio",
                      "taxa_amostragem", "canais"):
            tecnico.pop(chave, None)

    return {
        "indice": indice,
        "disco": disco,
        "tecnico": tecnico,
        "mime": mime,
        "origem": origem,
    }
