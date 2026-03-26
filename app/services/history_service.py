from datetime import datetime

from app.core.constants import BR_TZ, DISK_PATH
from app.repositories.history_repository import insert_daily_history, get_history_rows
from app.services.status_service import StatusService


class HistoryService:
    @staticmethod
    def save_daily_history():
        disk = StatusService.get_disk_usage(DISK_PATH)
        today = datetime.now(tz=BR_TZ).strftime("%Y-%m-%d")
        insert_daily_history(today, disk["used_tb"])

    @staticmethod
    def get_history():
        rows = get_history_rows()
        return {
            "dates": [r["date"] for r in rows],
            "values": [r["used_tb"] for r in rows],
        }