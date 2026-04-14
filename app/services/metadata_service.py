from datetime import datetime
from typing import Any, Dict, List, Optional


BASE_METADATA_KEYS = {"title", "description", "campaign", "status", "is_official"}


def normalize_tags(tags: Optional[List[str]]) -> List[str]:
    if not tags:
        return []

    seen = set()
    normalized = []

    for tag in tags:
        if not tag:
            continue

        clean = str(tag).strip().lower()
        if not clean:
            continue

        if clean not in seen:
            seen.add(clean)
            normalized.append(clean)

    return normalized


def get_file_metadata(conn, file_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT
            id,
            title,
            description,
            campaign,
            status,
            is_official,
            metadata_updated_at
        FROM files_meta
        WHERE id = ?
        """,
        (file_id,),
    ).fetchone()

    if not row:
        return None

    tags_rows = conn.execute(
        """
        SELECT tag
        FROM file_tags
        WHERE file_id = ?
        ORDER BY tag ASC
        """,
        (file_id,),
    ).fetchall()

    meta_rows = conn.execute(
        """
        SELECT meta_key, meta_value
        FROM file_metadata
        WHERE file_id = ?
        ORDER BY meta_key ASC
        """,
        (file_id,),
    ).fetchall()

    extra_metadata = {r["meta_key"]: r["meta_value"] for r in meta_rows}

    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "campaign": row["campaign"],
        "status": row["status"],
        "is_official": bool(row["is_official"]),
        "metadata_updated_at": row["metadata_updated_at"],
        "tags": [tag_row["tag"] for tag_row in tags_rows],
        "metadata": extra_metadata,
    }


def update_file_metadata(conn, file_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    existing = conn.execute(
        "SELECT id FROM files_meta WHERE id = ?",
        (file_id,),
    ).fetchone()

    if not existing:
        return None

    set_clauses = []
    values = []

    fixed_fields = ["title", "description", "campaign", "status"]

    for field in fixed_fields:
        if field in payload:
            set_clauses.append(f"{field} = ?")
            values.append(payload[field])

    if "is_official" in payload:
        set_clauses.append("is_official = ?")
        values.append(1 if payload["is_official"] else 0)

    set_clauses.append("metadata_updated_at = ?")
    values.append(datetime.utcnow().isoformat())

    values.append(file_id)

    conn.execute(
        f"UPDATE files_meta SET {', '.join(set_clauses)} WHERE id = ?",
        values,
    )

    if "tags" in payload:
        tags = normalize_tags(payload["tags"])
        conn.execute("DELETE FROM file_tags WHERE file_id = ?", (file_id,))
        if tags:
            conn.executemany(
                "INSERT INTO file_tags (file_id, tag) VALUES (?, ?)",
                [(file_id, tag) for tag in tags],
            )

    if "metadata" in payload and isinstance(payload["metadata"], dict):
        metadata = payload["metadata"]

        conn.execute("DELETE FROM file_metadata WHERE file_id = ?", (file_id,))

        rows_to_insert = []
        for key, value in metadata.items():
            clean_key = str(key).strip()
            if not clean_key:
                continue

            if clean_key in BASE_METADATA_KEYS:
                continue

            rows_to_insert.append(
                (
                    file_id,
                    clean_key,
                    "" if value is None else str(value),
                    datetime.utcnow().isoformat(),
                )
            )

        if rows_to_insert:
            conn.executemany(
                """
                INSERT INTO file_metadata (file_id, meta_key, meta_value, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                rows_to_insert,
            )

    conn.commit()
    return get_file_metadata(conn, file_id)


def get_all_tags(conn, limit: int = 100) -> List[str]:
    rows = conn.execute(
        """
        SELECT tag, COUNT(*) as total
        FROM file_tags
        GROUP BY tag
        ORDER BY total DESC, tag ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return [row["tag"] for row in rows]