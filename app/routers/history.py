from fastapi import APIRouter

from app.services.history_service import HistoryService

router = APIRouter()


@router.get("/api/history")
def history():
    return HistoryService.get_history()