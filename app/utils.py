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
