from datetime import datetime

from app.core.constants import BR_TZ
from app.core.logger import logger
from app.repositories.activities_repository import (
    clear_all_activities,
    insert_activity,
    list_activities,
    list_activities_for_user,
)


class ActivityService:
    @staticmethod
    def log(
        action: str,
        filename: str | None,
        rel_path: str | None,
        current_user: dict | None = None,
    ):
        try:
            insert_activity(
                user_id=current_user.get("user_id") if current_user else None,
                user_email=current_user.get("sub") if current_user else None,
                user_name=current_user.get("name") if current_user else None,
                action=action,
                filename=filename,
                rel_path=rel_path,
                created_at=datetime.now(tz=BR_TZ).isoformat(),
            )
        except Exception:
            logger.exception("Falha ao registrar atividade")

    @staticmethod
    def _serialize(rows):
        return [
            {
                "user_id": r["user_id"],
                "user_email": r["user_email"],
                "user_name": r["user_name"],
                "action": r["action"],
                "filename": r["filename"],
                "rel_path": r["rel_path"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    @staticmethod
    def recent(limit: int):
        limit = max(1, min(limit, 100))
        rows = list_activities(limit)
        return ActivityService._serialize(rows)

    @staticmethod
    def recent_for_user(user_id: int, limit: int):
        limit = max(1, min(limit, 100))
        rows = list_activities_for_user(user_id, limit)
        return ActivityService._serialize(rows)

    @staticmethod
    def clear(current_user: dict | None = None):
        clear_all_activities()
        ActivityService.log("clear_activities", None, None, current_user=current_user)
        return {"ok": True}