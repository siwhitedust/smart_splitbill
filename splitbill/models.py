from django.db import models
from django.utils import timezone
import zoneinfo


class ActivityLog(models.Model):
    """
    Model Log Aktivitas Pengguna Smart Splitbill.
    Disimpan di database SQLite lokal dengan batas maksimal 50 data terbaru.
    """
    action = models.CharField(max_length=150, help_text="Jenis aksi atau aktivitas")
    ip = models.CharField(max_length=50, default='127.0.0.1', help_text="Alamat IP pengguna")
    details = models.TextField(blank=True, default='', help_text="Rincian informasi aktivitas")
    status = models.CharField(max_length=20, default='success', help_text="Status aksi: success, warning, error")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Log Aktivitas'
        verbose_name_plural = 'Log Aktivitas'

    def __str__(self):
        return f"[{self.created_at}] {self.action} ({self.ip})"

    def to_dict(self):
        jakarta_tz = zoneinfo.ZoneInfo("Asia/Jakarta")
        local_dt = self.created_at.astimezone(jakarta_tz)
        return {
            "id": self.id,
            "timestamp": local_dt.strftime("%d/%m/%Y %H:%M:%S WIB"),
            "action": self.action,
            "ip": self.ip,
            "details": self.details,
            "status": self.status,
        }
