"""
Service Logging Aktivitas Pengguna Berbasis Database SQLite.
Menyimpan dan mengelola hingga 50 aktivitas terbaru di database SQLite.
Setiap ada log baru ke-51, data paling lama otomatis dipangkas (dihapus).
"""

from typing import List, Dict, Any, Optional
from django.db import transaction
from splitbill.models import ActivityLog

MAX_LOG_ENTRIES = 50


class ActivityLogService:
    """
    Mengelola pencatatan log aktivitas pemrosesan struk, pembagian tagihan,
    dan aksi admin di dalam database SQLite lokal.
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
        Mencatat satu entri log aktivitas baru ke database SQLite.
        Menjaga maksimal 50 log terakhir (data ke-51 dan seterusnya otomatis dihapus).
        """
        clean_ip = ip or "127.0.0.1"
        try:
            with transaction.atomic():
                entry = ActivityLog.objects.create(
                    action=action,
                    ip=clean_ip,
                    details=details,
                    status=status,
                )

                # Pruning otomatis: jika total entri melebihi MAX_LOG_ENTRIES, hapus yang terlama
                excess_ids = list(
                    ActivityLog.objects.order_by('-created_at', '-id')[MAX_LOG_ENTRIES:]
                    .values_list('id', flat=True)
                )
                if excess_ids:
                    ActivityLog.objects.filter(id__in=excess_ids).delete()

            return entry.to_dict()
        except Exception:
            # Fallback jika terjadi error database tak terduga
            from splitbill.utils import get_jakarta_now
            now = get_jakarta_now()
            return {
                "id": 0,
                "timestamp": now.strftime("%d/%m/%Y %H:%M:%S WIB"),
                "action": action,
                "ip": clean_ip,
                "details": details,
                "status": status,
            }

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Mengambil daftar log aktivitas terbaru dari database SQLite.
        """
        try:
            qs = ActivityLog.objects.order_by('-created_at', '-id')[:limit]
            return [item.to_dict() for item in qs]
        except Exception:
            return []

    def clear_logs(self) -> bool:
        """
        Membersihkan seluruh log aktivitas dari database SQLite.
        """
        try:
            ActivityLog.objects.all().delete()
            return True
        except Exception:
            return False


activity_log_service = ActivityLogService()
