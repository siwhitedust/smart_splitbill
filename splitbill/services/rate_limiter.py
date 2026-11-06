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
    Mengelola batasan pemrosesan OCR harian strictly berbasis Alamat IP jaringan.
    Maksimal 5x per hari per IP address.
    Menutup celah incognito, hapus cookie, ganti profil browser, atau ganti session.
    """

    def __init__(self, daily_limit: int = DAILY_LIMIT):
        self.daily_limit = daily_limit

    def _hash_ip(self, ip: str) -> str:
        """Menghasilkan hash sha256 24 karakter dari IP."""
        return hashlib.sha256((ip or "127.0.0.1").encode('utf-8')).hexdigest()[:24]

    def _get_identifier(self, request) -> str:
        """
        Menghasilkan hash unik strictly berbasis Alamat IP klien (REMOTE_ADDR).
        Menjamin bahwa penghapusan cookie atau pembukaan tab incognito dari IP yang sama
        tidak akan mereset kuota harian.
        """
        ip = get_client_ip(request)
        return self._hash_ip(ip)

    def _track_active_ip(self, ip: str, date_str: str, ttl: int):
        """Mencatat IP aktif hari ini ke cache untuk manajemen reset kuota admin."""
        if not ip:
            return
        active_key = f"splitbill:rate_limit:active_ips:{date_str}"
        active_ips = cache.get(active_key, [])
        if not isinstance(active_ips, list):
            active_ips = []
        if ip not in active_ips:
            active_ips.append(ip)
            cache.set(active_key, active_ips, timeout=ttl)

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
        ip = get_client_ip(request)
        key, ttl = self._get_cache_key_and_ttl(request)
        now = get_jakarta_now()
        date_str = now.strftime("%Y%m%d")
        self._track_active_ip(ip, date_str, ttl)

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
        ip = get_client_ip(request)
        return self.reset_quota_by_ip(ip)

    def reset_quota_by_ip(self, ip: str) -> bool:
        """
        Mereset kuota OCR untuk satu IP pengguna tertentu pada hari ini.
        """
        now = get_jakarta_now()
        date_str = now.strftime("%Y%m%d")
        ident = self._hash_ip(ip)
        key = f"splitbill:rate_limit:ocr:{date_str}:{ident}"
        cache.delete(key)
        return True

    def reset_all_quotas(self) -> int:
        """
        Mereset kuota OCR seluruh pengguna yang aktif tercatat hari ini.
        Mengembalikan jumlah pengguna yang direset.
        """
        now = get_jakarta_now()
        date_str = now.strftime("%Y%m%d")
        active_key = f"splitbill:rate_limit:active_ips:{date_str}"
        active_ips = cache.get(active_key, [])
        if not isinstance(active_ips, list):
            active_ips = []

        count = 0
        for ip in active_ips:
            ident = self._hash_ip(ip)
            key = f"splitbill:rate_limit:ocr:{date_str}:{ident}"
            cache.delete(key)
            count += 1

        cache.delete(active_key)
        return count

    def get_status_for_ip(self, ip: str) -> Tuple[bool, int, int]:
        """
        Mendapatkan status kuota (is_allowed, used_count, remaining) untuk IP tertentu.
        """
        now = get_jakarta_now()
        date_str = now.strftime("%Y%m%d")
        ident = self._hash_ip(ip)
        key = f"splitbill:rate_limit:ocr:{date_str}:{ident}"
        current = cache.get(key, 0)
        remaining = max(0, self.daily_limit - current)
        is_allowed = current < self.daily_limit
        return is_allowed, current, remaining


rate_limiter = RateLimiterService()

