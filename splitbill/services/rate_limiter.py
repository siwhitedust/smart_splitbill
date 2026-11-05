"""
Layer rate limiting untuk membatasi analisis struk OCR.
Maksimal 5x per hari per identitas (kombinasi IP address dan session ID).
Perhitungan hari merujuk pada zona waktu Asia/Jakarta.
"""

import hashlib
from datetime import datetime, time as dt_time, timedelta
from typing import Tuple
from django.core.cache import cache
from django.conf import settings
from splitbill.utils import get_client_ip, get_jakarta_now, JAKARTA_TZ

DAILY_LIMIT = getattr(settings, 'RATE_LIMIT_DAILY_MAX', 5)


class RateLimiterService:
    """
    Mengelola batasan pemrosesan OCR harian berbasis IP dan Session.
    """

    def __init__(self, daily_limit: int = DAILY_LIMIT):
        self.daily_limit = daily_limit

    def _get_identifier(self, request) -> str:
        """
        Menghasilkan hash unik dari kombinasi IP address dan Session key.
        """
        ip = get_client_ip(request)
        # Pastikan session ada atau dibuatkan session key
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key or 'nosession'

        raw = f"{ip}:{session_key}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]

    def _get_cache_key_and_ttl(self, request) -> Tuple[str, int]:
        """
        Mendapatkan cache key untuk hari ini (Asia/Jakarta) dan sisa detik sampai tengah malam.
        """
        now = get_jakarta_now()
        date_str = now.strftime("%Y%m%d")
        ident = self._get_identifier(request)
        key = f"splitbill:rate_limit:ocr:{date_str}:{ident}"

        # Hitung detik sampai jam 23:59:59 Jakarta
        midnight = datetime.combine(now.date() + timedelta(days=1), dt_time.min, tzinfo=JAKARTA_TZ)
        seconds_until_midnight = max(60, int((midnight - now).total_seconds()))

        return key, seconds_until_midnight

    def get_status(self, request) -> Tuple[bool, int, int]:
        """
        Mengecek status kuota tanpa menambah hitungan.
        Mengembalikan: (is_allowed, current_count, remaining_quota)
        """
        key, _ = self._get_cache_key_and_ttl(request)
        current = cache.get(key, 0)
        remaining = max(0, self.daily_limit - current)
        is_allowed = current < self.daily_limit
        return is_allowed, current, remaining

    def consume_quota(self, request) -> Tuple[bool, int, str]:
        """
        Mencoba menggunakan 1 kuota harian OCR.
        Jika diizinkan, tambahkan hitungan dan kembalikan (True, remaining, "").
        Jika batas tercapai, kembalikan (False, 0, pesan error).
        """
        key, ttl = self._get_cache_key_and_ttl(request)
        current = cache.get(key, 0)

        if current >= self.daily_limit:
            msg = "kuota 1 hari sudah habis see you besok"
            return False, 0, msg

        new_count = current + 1
        cache.set(key, new_count, timeout=ttl)
        remaining = max(0, self.daily_limit - new_count)
        return True, remaining, ""

    def reset_quota(self, request) -> bool:
        """
        Mereset kuota OCR harian identitas saat ini (khusus keperluan development/testing).
        """
        key, _ = self._get_cache_key_and_ttl(request)
        cache.delete(key)
        return True


rate_limiter = RateLimiterService()

