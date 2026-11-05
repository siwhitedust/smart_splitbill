"""
Layer service pengelolaan cache untuk Smart Splitbill.
Menangani penyimpanan tagihan dengan TTL tepat 600 detik (10 menit).
Didesain modular sehingga siap berganti antara LocMemCache dan Redis.
"""

import time
from typing import Optional, Dict, Any, List
from django.core.cache import cache
from django.conf import settings
from splitbill.utils import generate_bill_token, get_jakarta_now

CACHE_PREFIX = "splitbill:bill:"
DEFAULT_TTL = getattr(settings, 'SPLITBILL_TTL_SECONDS', 600)  # 600 detik (10 menit)
SESSION_BILLS_KEY = "splitbill_saved_tokens"


class BillCacheService:
    """
    Service abstraksi untuk mengelola tagihan di cache (LocMemCache / Redis).
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL):
        self.ttl = ttl_seconds

    def _cache_key(self, token: str) -> str:
        return f"{CACHE_PREFIX}{token}"

    def save_bill(self, bill_data: Dict[str, Any], token: Optional[str] = None) -> str:
        """
        Menyimpan hasil perhitungan splitbill ke cache dengan TTL tepat 600 detik.
        Mengembalikan token URL unik.
        """
        if not token:
            token = generate_bill_token()

        key = self._cache_key(token)
        now_ts = time.time()
        expires_at_ts = now_ts + self.ttl

        # Lengkapi metadata tagihan
        payload = {
            **bill_data,
            'token': token,
            'created_at_ts': now_ts,
            'expires_at_ts': expires_at_ts,
            'ttl_seconds': self.ttl,
            'created_at_str': get_jakarta_now().strftime("%d %b %Y, %H:%M WIB"),
        }

        # Simpan ke cache dengan TTL 600 detik
        cache.set(key, payload, timeout=self.ttl)
        return token

    def get_bill(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Mengambil data tagihan dari cache berdasarkan token unik.
        Jika data tidak ada atau telah kedaluwarsa (> 600 detik), kembalikan None.
        Menghitung remaining_seconds secara realtime.
        """
        if not token:
            return None

        key = self._cache_key(token)
        data = cache.get(key)
        if not data:
            return None

        # Hitung sisa waktu kedaluwarsa
        now_ts = time.time()
        expires_at_ts = data.get('expires_at_ts', now_ts)
        remaining = int(expires_at_ts - now_ts)

        if remaining <= 0:
            # Data sudah kedaluwarsa
            cache.delete(key)
            return None

        data['remaining_seconds'] = remaining
        return data

    def delete_bill(self, token: str) -> bool:
        """Menghapus data tagihan dari cache."""
        key = self._cache_key(token)
        return cache.delete(key)

    def attach_bill_to_session(self, session, token: str):
        """
        Menyimpan token tagihan ke sesi pengguna agar riwayat aktif dapat ditampilkan di dashboard.
        """
        tokens = session.get(SESSION_BILLS_KEY, [])
        if token not in tokens:
            tokens.append(token)
            session[SESSION_BILLS_KEY] = tokens
            if hasattr(session, 'modified'):
                session.modified = True

    def get_user_active_bills(self, session) -> List[Dict[str, Any]]:
        """
        Mengambil seluruh tagihan aktif milik sesi pengguna yang belum kedaluwarsa.
        Jika tagihan sudah kedaluwarsa di cache, hapus token dari session.
        """
        tokens = session.get(SESSION_BILLS_KEY, [])
        active_bills = []
        valid_tokens = []

        for token in tokens:
            bill = self.get_bill(token)
            if bill:
                active_bills.append(bill)
                valid_tokens.append(token)

        # Perbarui token di session hanya yang masih aktif
        if len(valid_tokens) != len(tokens):
            session[SESSION_BILLS_KEY] = valid_tokens
            if hasattr(session, 'modified'):
                session.modified = True

        # Urutkan berdasarkan waktu pembuatan terbaru
        active_bills.sort(key=lambda x: x.get('created_at_ts', 0), reverse=True)
        return active_bills


# Global singleton instance
bill_cache_service = BillCacheService()
