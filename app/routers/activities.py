from fastapi import APIRouter, Query

from app.services.activity_service import ActivityService

router = APIRouter()


@router.get("/api/activities")
def recent_activities(limit: int = Query(10)):
    return ActivityService.recent(limit)


@router.post("/api/activities/clear")
def clear_activities():
    return ActivityService.clear()