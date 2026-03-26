import hashlib


def path_hash(path: str) -> str:
    return hashlib.md5(path.encode()).hexdigest()
