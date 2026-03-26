from datetime import datetime

from app.core.constants import BR_TZ
from app.core.logger import logger
from app.repositories.activities_repository import (
    insert_activity,
    list_activities,
    clear_all_activities,
)


class ActivityService:
    @staticmethod
    def log(action: str, filename: str | None, rel_path: str | None):
        try:
            insert_activity(
                action=action,
                filename=filename,
                rel_path=rel_path,
                created_at=datetime.now(tz=BR_TZ).isoformat(),
            )
        except Exception:
            logger.exception("Falha ao registrar atividade")

    @staticmethod
    def recent(limit: int):
        limit = max(1, min(limit, 100))
        rows = list_activities(limit)
        return [
            {
                "action": r["action"],
                "filename": r["filename"],
                "rel_path": r["rel_path"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    @staticmethod
    def clear():
        clear_all_activities()
        ActivityService.log("clear_activities", None, None)
        return {"ok": True}