"""
Backfill de content_hash para linhas já indexadas antes da coluna existir.
Rodar uma vez (a partir da raiz do repo): python -m scripts.backfill_content_hash

O indexer/watcher normais só calculam hash em arquivos novos/alterados; arquivos
"unchanged" nunca passam de novo pelo cálculo. Este script cobre o backlog inicial.
"""

import os
import time

from app.core.constants import DB_PATH, ROOT_DIR
from app.db import connect, ensure_files_schema, ensure_content_hash_column
from app.utils import content_hash_of_file, should_hash_content

BATCH_SIZE = 500


def backfill() -> None:
    conn = connect(DB_PATH)
    ensure_files_schema(conn)
    ensure_content_hash_column(conn)
    cur = conn.cursor()

    total = cur.execute(
        "SELECT COUNT(*) FROM files_meta WHERE content_hash IS NULL"
    ).fetchone()[0]
    print(f"Arquivos sem content_hash: {total:,}".replace(",", "."))

    done = 0
    unreadable = 0
    skipped = 0
    t0 = time.time()

    while True:
        rows = cur.execute(
            "SELECT id, rel_path FROM files_meta WHERE content_hash IS NULL LIMIT ?",
            (BATCH_SIZE,),
        ).fetchall()
        if not rows:
            break

        updates = []
        for row in rows:
            # subárvore de rede marcada como 'não hashear': grava "" sem ler o arquivo
            if not should_hash_content(row["rel_path"]):
                skipped += 1
                updates.append(("", row["id"]))
                continue
            full_path = os.path.join(ROOT_DIR, row["rel_path"])
            h = content_hash_of_file(full_path)
            if h is None:
                unreadable += 1
                # marca com string vazia pra não entrar de novo no WHERE content_hash IS NULL
                h = ""
            updates.append((h, row["id"]))

        cur.executemany(
            "UPDATE files_meta SET content_hash=? WHERE id=?", updates
        )
        conn.commit()

        done += len(rows)
        elapsed = time.time() - t0
        speed = done / elapsed if elapsed > 0 else 0
        print(f"  {done:,}/{total:,} ({speed:.0f} arquivos/s)".replace(",", "."))

    conn.close()
    print(f"Concluído. {unreadable} ilegível(is)/ausente(s) e {skipped} em subárvore de rede — marcados sem hash.")


if __name__ == "__main__":
    backfill()
