"""
Unit test untuk rate limiter harian analisis struk OCR:
- Maksimal 5x per hari per identitas (IP + Session)
- Pergantian hari merujuk zona waktu Asia/Jakarta
- Pesan kuota habis yang informatif
"""

from django.test import SimpleTestCase, RequestFactory
from django.core.cache import cache
from django.contrib.sessions.middleware import SessionMiddleware
from splitbill.services.rate_limiter import RateLimiterService


class RateLimiterTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.limiter = RateLimiterService(daily_limit=5)

    def tearDown(self):
        cache.clear()

    def _create_mock_request(self, ip='192.168.1.10'):
        request = self.factory.post('/api/ocr/', REMOTE_ADDR=ip)
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_consume_quota_up_to_limit(self):
        """Uji konsumsi kuota dari 5 sampai habis pada pemanggilan ke-6."""
        req = self._create_mock_request()

        # Pemanggilan 1 s.d. 5 harus diizinkan
        for i in range(1, 6):
            allowed, remaining, err = self.limiter.consume_quota(req)
            self.assertTrue(allowed)
            self.assertEqual(remaining, 5 - i)
            self.assertEqual(err, "")

        # Pemanggilan ke-6 harus ditolak
        allowed, remaining, err = self.limiter.consume_quota(req)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)
        self.assertEqual(err, "kuota 1 hari sudah habis see you besok")

    def test_different_ip_has_independent_quota(self):
        """Identitas IP yang berbeda memiliki kuota terpisah."""
        req1 = self._create_mock_request(ip='10.0.0.1')
        req2 = self._create_mock_request(ip='10.0.0.2')

        # Habiskan kuota req1
        for _ in range(5):
            self.limiter.consume_quota(req1)

        # req1 habis
        allowed1, _, _ = self.limiter.consume_quota(req1)
        self.assertFalse(allowed1)

        # req2 masih penuh
        allowed2, rem2, _ = self.limiter.consume_quota(req2)
        self.assertTrue(allowed2)
        self.assertEqual(rem2, 4)

    def test_clearing_cookies_or_session_does_not_reset_quota(self):
        """Menghapus cookie / ganti session (incognito) tidak mereset kuota karena terkunci strictly pada IP."""
        req1 = self._create_mock_request(ip='192.168.1.10')
        for _ in range(5):
            self.limiter.consume_quota(req1)

        # req1 kuota habis
        allowed1, _, _ = self.limiter.consume_quota(req1)
        self.assertFalse(allowed1)

        # Simulasi pengguna buka Incognito atau hapus cookie (session baru, IP sama)
        req2 = self._create_mock_request(ip='192.168.1.10')
        req2.session.flush()
        req2.session.save()
        self.assertNotEqual(req1.session.session_key, req2.session.session_key)

        # Harus tetap ditolak (0 kuota)
        allowed2, rem2, _ = self.limiter.consume_quota(req2)
        self.assertFalse(allowed2)
        self.assertEqual(rem2, 0)

    def test_x_forwarded_for_spoofing_is_ignored(self):
        """Header HTTP_X_FORWARDED_FOR diabaikan, identitas tetap membaca REMOTE_ADDR asli."""
        req = self._create_mock_request(ip='192.168.1.50')
        for _ in range(5):
            self.limiter.consume_quota(req)

        # Coba spoof header X-Forwarded-For dengan IP acak lain
        req_spoof = self.factory.post(
            '/api/ocr/',
            REMOTE_ADDR='192.168.1.50',
            HTTP_X_FORWARDED_FOR='8.8.8.8, 1.1.1.1'
        )
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(req_spoof)
        req_spoof.session.save()

        allowed, rem, _ = self.limiter.consume_quota(req_spoof)
        self.assertFalse(allowed)
        self.assertEqual(rem, 0)

    def test_reset_quota_by_ip(self):
        """Mereset kuota untuk IP tertentu mengembalikan kuota IP tersebut ke 5."""
        req = self._create_mock_request(ip='192.168.1.88')
        for _ in range(5):
            self.limiter.consume_quota(req)

        # Cek kuota habis
        _, used, rem = self.limiter.get_status_for_ip('192.168.1.88')
        self.assertEqual(used, 5)
        self.assertEqual(rem, 0)

        # Reset kuota IP ini
        self.limiter.reset_quota_by_ip('192.168.1.88')

        # Cek kuota kembali penuh
        _, used2, rem2 = self.limiter.get_status_for_ip('192.168.1.88')
        self.assertEqual(used2, 0)
        self.assertEqual(rem2, 5)

    def test_reset_all_quotas(self):
        """Mereset seluruh kuota menghapus semua batasan IP yang aktif hari ini."""
        req1 = self._create_mock_request(ip='10.10.1.1')
        req2 = self._create_mock_request(ip='10.10.1.2')
        self.limiter.consume_quota(req1)
        self.limiter.consume_quota(req2)

        reset_count = self.limiter.reset_all_quotas()
        self.assertGreaterEqual(reset_count, 2)

        _, used1, rem1 = self.limiter.get_status_for_ip('10.10.1.1')
        _, used2, rem2 = self.limiter.get_status_for_ip('10.10.1.2')
        self.assertEqual(rem1, 5)
        self.assertEqual(rem2, 5)


class ActivityLogServiceTest(SimpleTestCase):
    def setUp(self):
        from splitbill.services.activity_log_service import activity_log_service
        self.log_service = activity_log_service
        self.log_service.clear_logs()

    def tearDown(self):
        self.log_service.clear_logs()

    def test_log_and_retrieve_entries(self):
        """Log aktivitas dicatat di cache dan dapat diambil kembali dengan urutan FIFO (terbaru di atas)."""
        self.log_service.log(action="OCR Struk", ip="192.168.1.5", details="Resto Padang", status="success")
        self.log_service.log(action="Simpan Splitbill", ip="192.168.1.6", details="Grand Total 50k", status="success")

        logs = self.log_service.get_logs(limit=10)
        self.assertEqual(len(logs), 2)
        # Urutan terbaru paling atas
        self.assertEqual(logs[0]['action'], "Simpan Splitbill")
        self.assertEqual(logs[1]['action'], "OCR Struk")

    def test_log_service_max_limit_50(self):
        """Log dibatasi maksimal 50 entri terbaru."""
        for i in range(60):
            self.log_service.log(action=f"Aksi {i}", ip="127.0.0.1", details=f"Detail {i}")

        logs = self.log_service.get_logs(limit=100)
        self.assertEqual(len(logs), 50)
        self.assertEqual(logs[0]['action'], "Aksi 59")

    def test_clear_logs(self):
        """Membersihkan seluruh log di cache."""
        self.log_service.log(action="Test", ip="127.0.0.1")
        self.assertEqual(len(self.log_service.get_logs()), 1)

        self.log_service.clear_logs()
        self.assertEqual(len(self.log_service.get_logs()), 0)

