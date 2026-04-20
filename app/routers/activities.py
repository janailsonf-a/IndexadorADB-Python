from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth import get_current_user, require_admin
from app.services.activity_service import ActivityService

router = APIRouter()


class ActivityLogRequest(BaseModel):
    action: str
    filename: str | None = None
    rel_path: str | None = None


@router.get("/api/activities")
def recent_activities(
    limit: int = Query(10),
    current_user: dict = Depends(require_admin),
):
    return ActivityService.recent(limit)


@router.get("/api/activities/me")
def my_recent_activities(
    limit: int = Query(10),
    current_user: dict = Depends(get_current_user),
):
    return ActivityService.recent_for_user(current_user["user_id"], limit)


@router.post("/api/activities/log")
def log_activity(
    payload: ActivityLogRequest,
    current_user: dict = Depends(get_current_user),
):
    ActivityService.log(
        action=payload.action,
        filename=payload.filename,
        rel_path=payload.rel_path,
        current_user=current_user,
    )
    return {"ok": True}


@router.post("/api/activities/clear")
def clear_activities(current_user: dict = Depends(require_admin)):
    return ActivityService.clear(current_user=current_user)