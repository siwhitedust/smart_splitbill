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

    def test_reset_quota_restores_limit(self):
        """Uji fungsi reset_quota mengembalikan kuota penuh."""
        req = self._create_mock_request(ip='10.0.0.5')
        for _ in range(5):
            self.limiter.consume_quota(req)

        # Sudah habis
        allowed, rem, _ = self.limiter.consume_quota(req)
        self.assertFalse(allowed)

        # Reset kuota
        self.limiter.reset_quota(req)

        # Kuota harus kembali tersedia
        is_allowed, count, remaining = self.limiter.get_status(req)
        self.assertTrue(is_allowed)
        self.assertEqual(remaining, 5)

