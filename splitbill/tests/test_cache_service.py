"""
Unit test untuk layer cache temporary:
- Penyimpanan tagihan dengan TTL 600 detik
- Pengambilan tagihan aktif & perhitungan sisa waktu (remaining_seconds)
- Kedaluwarsa data (> 600 detik)
- Pengelolaan riwayat tagihan berbasis sesi pengguna
"""

import time
from django.test import SimpleTestCase
from django.core.cache import cache
from splitbill.services.cache_service import BillCacheService


class CacheServiceTest(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.service = BillCacheService(ttl_seconds=600)

    def tearDown(self):
        cache.clear()

    def test_save_and_retrieve_bill(self):
        """Uji menyimpan tagihan dan mengambilnya kembali dari cache."""
        bill_data = {
            'restaurant_name': 'Bakso Pak Kumis',
            'grand_total_formatted': 'Rp45.000',
            'participant_count': 2,
        }

        token = self.service.save_bill(bill_data)
        self.assertIsNotNone(token)
        self.assertTrue(len(token) >= 12)

        # Ambil kembali
        retrieved = self.service.get_bill(token)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved['restaurant_name'], 'Bakso Pak Kumis')
        self.assertEqual(retrieved['token'], token)
        self.assertTrue(595 <= retrieved['remaining_seconds'] <= 600)

    def test_invalid_or_expired_token_returns_none(self):
        """Token yang tidak terdaftar harus mengembalikan None."""
        self.assertIsNone(self.service.get_bill('tokenNonExistent123'))
        self.assertIsNone(self.service.get_bill(''))
        self.assertIsNone(self.service.get_bill(None))

    def test_bill_expiration_simulation(self):
        """Uji kedaluwarsa tagihan menggunakan TTL pendek (2 detik)."""
        short_service = BillCacheService(ttl_seconds=2)
        token = short_service.save_bill({'restaurant_name': 'Kedai Kopi'})

        # Masih ada sesaat setelah disimpan
        self.assertIsNotNone(short_service.get_bill(token))

        # Tunggu hingga melewati 2 detik
        time.sleep(2.2)
        # Seharusnya sudah expired dan mengembalikan None
        self.assertIsNone(short_service.get_bill(token))

    def test_session_bill_tracking(self):
        """Uji kaitan riwayat tagihan aktif dengan session pengguna."""
        mock_session = {}

        token1 = self.service.save_bill({'restaurant_name': 'Resto A', 'grand_total_formatted': 'Rp50.000', 'participant_count': 2})
        token2 = self.service.save_bill({'restaurant_name': 'Resto B', 'grand_total_formatted': 'Rp75.000', 'participant_count': 3})

        self.service.attach_bill_to_session(mock_session, token1)
        self.service.attach_bill_to_session(mock_session, token2)

        active = self.service.get_user_active_bills(mock_session)
        self.assertEqual(len(active), 2)

        # Hapus token1 (simulasi expired)
        self.service.delete_bill(token1)

        # Hanya token2 yang harus muncul
        active_after = self.service.get_user_active_bills(mock_session)
        self.assertEqual(len(active_after), 1)
        self.assertEqual(active_after[0]['restaurant_name'], 'Resto B')
