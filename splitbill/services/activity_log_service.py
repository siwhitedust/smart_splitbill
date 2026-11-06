"""
Service Logging Aktivitas Pengguna Berbasis Memory Cache.
Menyimpan hingga 50 aktivitas terbaru di cache tanpa memerlukan tabel database baru.
"""

import time
from typing import List, Dict, Any, Optional
from django.core.cache import cache
from splitbill.utils import get_jakarta_now

CACHE_KEY_ACTIVITY_LOGS = "splitbill:activity_logs"
MAX_LOG_ENTRIES = 50
LOG_TTL_SECONDS = 86400 * 7  # Simpan selama 7 hari di cache


class ActivityLogService:
    """
    Mengelola pencatatan log aktivitas pemrosesan struk, pembagian tagihan,
    dan aksi admin di dalam memory cache.
    """

    def log(
        self,
        action: str,
        ip: str,
        details: str = "",
        status: str = "success",
        user_identifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mencatat satu entri log aktivitas baru ke memory cache.
        Menjaga maksimal 50 log terakhir (antrean FIFO, urutan terbaru di atas).
        """
        now = get_jakarta_now()
        entry: Dict[str, Any] = {
            "id": int(time.time() * 1000),
            "timestamp": now.strftime("%d/%m/%Y %H:%M:%S WIB"),
            "action": action,
            "ip": ip or "127.0.0.1",
            "details": details,
            "status": status,  # 'success', 'warning', 'error'
        }

        try:
            logs: List[Dict[str, Any]] = cache.get(CACHE_KEY_ACTIVITY_LOGS, [])
            if not isinstance(logs, list):
                logs = []

            # Sisipkan ke awal list (terbaru paling atas)
            logs.insert(0, entry)
            if len(logs) > MAX_LOG_ENTRIES:
                logs = logs[:MAX_LOG_ENTRIES]

            cache.set(CACHE_KEY_ACTIVITY_LOGS, logs, timeout=LOG_TTL_SECONDS)
        except Exception:
            pass

        return entry

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Mengambil daftar log aktivitas terbaru dari cache.
        """
        try:
            logs = cache.get(CACHE_KEY_ACTIVITY_LOGS, [])
            if not isinstance(logs, list):
                return []
            return logs[:limit]
        except Exception:
            return []

    def clear_logs(self) -> bool:
        """
        Membersihkan seluruh log aktivitas dari cache.
        """
        try:
            cache.delete(CACHE_KEY_ACTIVITY_LOGS)
            return True
        except Exception:
            return False


activity_log_service = ActivityLogService()

