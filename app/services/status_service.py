import os
import shutil
import subprocess
from datetime import datetime

import psutil

from app.config import settings
from app.core.constants import BR_TZ, DISK_PATH
from app.core.logger import logger
from app.repositories.db_connection import db_connect
from app.repositories.status_repository import db_count_files, get_indexer_status_data


class StatusService:
    @staticmethod
    def get_disk_usage(path: str):
        total, used, free = shutil.disk_usage(path)
        return {
            "total_tb": round(total / (1024 ** 4), 2),
            "used_tb": round(used / (1024 ** 4), 2),
            "free_tb": round(free / (1024 ** 4), 2),
            "usage_percent": round((used / total) * 100, 1),
            "path": path,
        }

    @staticmethod
    def get_system_metrics():
        return {
            "cpu": psutil.cpu_percent(interval=0.2),
            "ram": psutil.virtual_memory().percent,
        }

    @staticmethod
    def get_services_status():
        try:
            result = subprocess.run(["pgrep", "-f", "rclone"], capture_output=True, text=True)
            rclone_active = bool(result.stdout.strip())
        except Exception:
            rclone_active = False
        return {"rclone_active": rclone_active}

    @staticmethod
    def get_recent_logs():
        log_path = settings.log_path
        if not os.path.exists(log_path):
            return "Sem logs ainda."
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-30:]
            return "".join(lines)
        except Exception:
            logger.exception("Falha ao ler logs")
            return "Não foi possível ler logs."

    @staticmethod
    def healthcheck():
        disk = StatusService.get_disk_usage(DISK_PATH)
        try:
            conn = db_connect()
            conn.execute("SELECT 1")
            conn.close()
            db_status = "ok"
        except Exception:
            logger.exception("Healthcheck do banco falhou")
            db_status = "fail"

        overall = "ok"
        if db_status != "ok" or disk["usage_percent"] > 95:
            overall = "degraded"

        return {
            "status": overall,
            "database": db_status,
            "disk_usage_percent": disk["usage_percent"],
            "disk_path": disk["path"],
            "time": datetime.now(tz=BR_TZ).isoformat(),
        }

    @staticmethod
    def api_status():
        disk = StatusService.get_disk_usage(DISK_PATH)
        metrics = StatusService.get_system_metrics()
        services = StatusService.get_services_status()

        disk_alert = disk["usage_percent"] > 90
        cpu_alert = metrics["cpu"] > 85
        ram_alert = metrics["ram"] > 85

        overall = "ok"
        if disk_alert or cpu_alert or ram_alert:
            overall = "warning"
        if disk["usage_percent"] > 95:
            overall = "critical"

        return {
            "overall_status": overall,
            "disk": disk,
            "metrics": metrics,
            "services": services,
            "alerts": {
                "disk_high": disk_alert,
                "cpu_high": cpu_alert,
                "ram_high": ram_alert,
            },
        }

    @staticmethod
    def full_status():
        return {
            "disk": StatusService.get_disk_usage(DISK_PATH),
            "metrics": StatusService.get_system_metrics(),
            "services": StatusService.get_services_status(),
            "indexer": get_indexer_status_data(),
            "time": datetime.now(tz=BR_TZ).isoformat(),
        }

    @staticmethod
    def status_page_context():
        return {
            "data": StatusService.api_status(),
            "idx": get_indexer_status_data(),
            "total_indexed": db_count_files(),
            "recent_logs": StatusService.get_recent_logs(),
        }