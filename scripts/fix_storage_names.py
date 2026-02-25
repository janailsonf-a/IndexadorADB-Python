import os
import re
import shutil
from datetime import datetime

ROOT_DIR = "/mnt/share"
LOG_FILE = "/opt/indexador/scripts/sanitize_log.txt"

INVALID_PATTERNS = [
    r"^#",
    r"^~\$",
    r"^\._",
    r"\s+$",
]

REPLACE_MAP = {
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
}

DRY_RUN = True  # 🔥 Mude para False quando for executar de verdade


def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg)


def sanitize_name(name):
    new_name = name

    # remover espaços extras no início/fim
    new_name = new_name.strip()

    # substituir caracteres especiais
    for k, v in REPLACE_MAP.items():
        new_name = new_name.replace(k, v)

    # remover #
    if new_name.startswith("#"):
        new_name = new_name.lstrip("#")

    return new_name


def should_ignore(name):
    for pattern in INVALID_PATTERNS:
        if re.search(pattern, name):
            return True
    return False


def process():
    log(f"\n===== EXECUÇÃO {datetime.now()} =====")

    for root, dirs, files in os.walk(ROOT_DIR):

        for name in files:
            if should_ignore(name):

                old_path = os.path.join(root, name)
                new_name = sanitize_name(name)
                new_path = os.path.join(root, new_name)

                if old_path == new_path:
                    continue

                log(f"[RENAME FILE] {old_path} -> {new_path}")

                if not DRY_RUN:
                    try:
                        shutil.move(old_path, new_path)
                    except Exception as e:
                        log(f"[ERROR] {e}")

        for name in dirs:
            if should_ignore(name):

                old_path = os.path.join(root, name)
                new_name = sanitize_name(name)
                new_path = os.path.join(root, new_name)

                if old_path == new_path:
                    continue

                log(f"[RENAME DIR] {old_path} -> {new_path}")

                if not DRY_RUN:
                    try:
                        shutil.move(old_path, new_path)
                    except Exception as e:
                        log(f"[ERROR] {e}")


if __name__ == "__main__":
    process()
