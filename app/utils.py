import os
import hashlib


def path_hash(path: str) -> str:
    return hashlib.md5(path.encode()).hexdigest()


def content_hash_of_file(full_path: str, chunk_size: int = 1024 * 1024) -> str | None:
    """SHA-256 do conteúdo do arquivo. None se não conseguir ler (permissão, symlink quebrado etc.)."""
    h = hashlib.sha256()
    try:
        with open(full_path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


# Subárvores onde NÃO calcular hash de conteúdo. Pensado para montagens de rede
# (CIFS/NFS): calcular SHA-256 lê cada byte de cada arquivo, o que sobre a rede
# leva horas e satura o link — sem contrapartida, já que esse conteúdo é
# somente-leitura e uma duplicata encontrada lá não poderia ser removida mesmo.
# Formato: prefixos de rel_path separados por vírgula. Ex: "_winmkt,_outro"
HASH_SKIP_PREFIXES = tuple(
    p.strip().strip("/")
    for p in os.getenv("HASH_SKIP_PREFIXES", "").split(",")
    if p.strip()
)


def should_hash_content(rel_path: str) -> bool:
    """False para caminhos em subárvores marcadas como 'não hashear' (ver acima)."""
    if not HASH_SKIP_PREFIXES:
        return True
    norm = (rel_path or "").replace("\\", "/").lstrip("/")
    # compara por limite de pasta: "_winmkt" nao pode casar "_winmkt2/..."
    return not any(norm == pre or norm.startswith(pre + "/") for pre in HASH_SKIP_PREFIXES)
