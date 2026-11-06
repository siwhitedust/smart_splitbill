"""
Pengujian Security & HTTP Endpoints Smart Splitbill:
- Proteksi upload file (ekstensi, ukuran, MIME)
- Rate limiting 429
- Token URL acak & read-only enforcement
- Tampilan 404 expired ramah tanpa bocoran traceback
"""

import io
import json
from unittest.mock import patch
from PIL import Image
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from splitbill.services.cache_service import bill_cache_service


class ViewsAndSecurityTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@splitbill.local', 'superadmin123')

    def tearDown(self):
        cache.clear()

    def test_dashboard_and_create_page_get(self):
        """Dashboard dan halaman create dapat diakses via GET."""
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Smart Splitbill")
        self.assertContains(resp, "Belum ada riwayat splitbill")

        resp_create = self.client.get('/buat/')
        self.assertEqual(resp_create.status_code, 200)
        self.assertContains(resp_create, "Upload atau Potret Struk")

    def test_upload_invalid_extension_rejected(self):
        """Upload file bukan gambar (.txt / .exe) harus ditolak."""
        fake_file = SimpleUploadedFile("danger.exe", b"binarycontent", content_type="application/octet-stream")
        resp = self.client.post('/api/ocr/', {'receipt_image': fake_file})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn("tidak didukung", data['message'])

    def test_upload_oversized_file_rejected(self):
        """Upload file lebih dari 5MB harus ditolak."""
        big_content = b"0" * (6 * 1024 * 1024)  # 6 MB
        big_file = SimpleUploadedFile("large_receipt.jpg", big_content, content_type="image/jpeg")
        resp = self.client.post('/api/ocr/', {'receipt_image': big_file})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("terlalu besar", data['message'])

    def test_save_bill_api_validation_and_success(self):
        """Uji endpoint simpan tagihan ke cache."""
        payload = {
            'bill_info': {
                'restaurant_name': 'Soto Betawi Bang Ali',
                'transaction_date': '2026-11-04',
                'subtotal': '50000',
                'tax': '5000',
                'service': '0',
                'discount': '0',
                'other_fees': '0',
                'grand_total': '55000',
            },
            'items': [
                {'id': 1, 'name': 'Soto Daging', 'qty': '1', 'price': '35000'},
                {'id': 2, 'name': 'Nasi Putih', 'qty': '2', 'price': '7500'},
            ],
            'participants': [
                {
                    'id': 1,
                    'name': 'Rian',
                    'items': [
                        {'item_id': 1, 'name': 'Soto Daging', 'qty': '1', 'price': '35000'},
                        {'item_id': 2, 'name': 'Nasi Putih', 'qty': '1', 'price': '7500'},
                    ]
                },
                {
                    'id': 2,
                    'name': 'Dina',
                    'items': [
                        {'item_id': 2, 'name': 'Nasi Putih', 'qty': '1', 'price': '7500'},
                    ]
                }
            ]
        }

        resp = self.client.post(
            '/api/simpan/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('token', data)
        self.assertIn('bill_url', data)

        token = data['token']

        # Buka halaman detail tagihan dengan token yang valid
        detail_resp = self.client.get(f'/tagihan/{token}')
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, "Soto Betawi Bang Ali")
        self.assertContains(detail_resp, "Rian")
        self.assertContains(detail_resp, "Dina")

    def test_invalid_or_expired_bill_returns_404_page(self):
        """Akses token yang tidak ada harus menampilkan halaman expired tanpa error server."""
        resp = self.client.get('/tagihan/tokenPalsuYangTidakAda')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, "tagihan ini sudah tidak tersedia atau telah kedaluwarsa", status_code=404)

    def test_bill_detail_is_readonly(self):
        """Halaman detail tagihan /tagihan/<token> hanya menerima GET (read-only)."""
        token = bill_cache_service.save_bill({'restaurant_name': 'Resto Test', 'participants': []})
        # Coba POST atau DELETE ke halaman detail
        resp_post = self.client.post(f'/tagihan/{token}', {'hacked': 'true'})
        # Harus ditolak (405 Method Not Allowed)
        self.assertEqual(resp_post.status_code, 405)

    @patch('splitbill.views.rate_limiter.get_status')
    def test_ocr_api_when_personal_quota_exhausted(self, mock_status):
        """Ketika kuota personal harian habis, API mengembalikan 429 'kuota 1 hari sudah habis see you besok'."""
        mock_status.return_value = (False, 5, 0)

        fake_img = SimpleUploadedFile("struk.jpg", b"fakecontent", content_type="image/jpeg")
        resp = self.client.post('/api/ocr/', {'receipt_image': fake_img})
        self.assertEqual(resp.status_code, 429)
        data = resp.json()
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'kuota 1 hari sudah habis see you besok')

    def test_reset_quota_endpoint_is_removed(self):
        """Endpoint /api/reset-kuota/ telah dihapus dan mengembalikan 404 Not Found."""
        resp = self.client.post('/api/reset-kuota/')
        self.assertEqual(resp.status_code, 404)

    @patch('splitbill.services.ocr_service.scan_receipt_gemini')
    def test_ocr_api_when_ai_quota_exhausted(self, mock_scan):
        """Ketika kuota model AI habis (429/quota), API mengembalikan 429 'kuota 1 hari sudah habis see you besok'."""
        mock_scan.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED: quota limit reached")

        fake_img = SimpleUploadedFile("struk.jpg", b"fakecontent", content_type="image/jpeg")
        resp = self.client.post('/api/ocr/', {'receipt_image': fake_img})
        self.assertEqual(resp.status_code, 429)
        data = resp.json()
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'kuota 1 hari sudah habis see you besok')

    @patch('splitbill.services.ocr_service.scan_receipt_gemini')
    def test_ocr_api_when_server_busy(self, mock_scan):
        """Ketika server Google sibuk (503 / semua model gagal), API mengembalikan 503 'server sedang sibuk'."""
        mock_scan.side_effect = RuntimeError(
            "Semua model (utama & cadangan) gagal memproses struk. Rincian kegagalan: "
            "gemini-2.5-flash: Kuota harian habis / Rate limit (429 RESOURCE_EXHAUSTED); "
            "gemini-2.0-flash: Model tidak tersedia / Dialihkan ke generasi terbaru (404 NOT_FOUND); "
            "gemini-2.5-flash-lite: Model tidak tersedia / Dialihkan ke generasi terbaru (404 NOT_FOUND); "
            "gemini-3.5-flash-lite: Server Google sedang sibuk / High demand (503 UNAVAILABLE)"
        )

        fake_img = SimpleUploadedFile("struk.jpg", b"fakecontent", content_type="image/jpeg")
        resp = self.client.post('/api/ocr/', {'receipt_image': fake_img})
        self.assertEqual(resp.status_code, 503)
        data = resp.json()
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'server sedang sibuk')

    @patch('splitbill.services.ocr_service.scan_receipt_gemini')
    def test_ocr_api_does_not_consume_quota(self, mock_scan):
        """Memproses OCR struk tidak langsung memotong kuota harian pengguna."""
        mock_scan.return_value = {
            "status": "success",
            "model_used": "gemini-3.5-flash-lite",
            "data": {
                "restaurant_name": "Warung Makan Enak",
                "items": [{"name": "Teh Manis", "qty": 1, "unit_price": 5000, "total_price": 5000}],
                "subtotal": 5000,
                "tax": 0,
                "service_charge": 0,
                "discount": 0,
                "grand_total": 5000
            }
        }
        # Reset dulu kuota
        cache.clear()

        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        fake_img = SimpleUploadedFile("struk.jpg", buf.getvalue(), content_type="image/jpeg")

        resp = self.client.post('/api/ocr/', {'receipt_image': fake_img})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['remaining_quota'], 5)

        # Cek status kuota di rate limiter masih 5 (belum terpotong)
        check_resp = self.client.get('/buat/')
        self.assertEqual(check_resp.context['remaining_quota'], 5)

    def test_save_bill_api_consumes_quota(self):
        """Menyimpan splitbill resmi (/api/simpan/) memotong 1 kuota harian."""
        cache.clear()
        payload = {
            'bill_info': {
                'restaurant_name': 'Soto Betawi',
                'transaction_date': '2026-11-05',
                'subtotal': '20000',
                'tax': '0',
                'service': '0',
                'discount': '0',
                'other_fees': '0',
                'grand_total': '20000',
            },
            'items': [
                {'id': 1, 'name': 'Soto', 'qty': '1', 'price': '20000'},
            ],
            'participants': [
                {
                    'id': 1,
                    'name': 'Rian',
                    'items': [{'item_id': 1, 'name': 'Soto', 'qty': '1', 'price': '20000'}]
                }
            ]
        }
        resp = self.client.post('/api/simpan/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['remaining_quota'], 4)

        # Simpan lagi
        resp2 = self.client.post('/api/simpan/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()['remaining_quota'], 3)

    @patch('splitbill.views.rate_limiter.get_status')
    def test_save_bill_api_when_quota_exhausted(self, mock_status):
        """Ketika kuota harian habis, simpan tagihan ditolak dengan HTTP 429."""
        mock_status.return_value = (False, 5, 0)
        payload = {
            'bill_info': {'restaurant_name': 'Resto'},
            'items': [{'id': 1, 'name': 'Item', 'qty': 1, 'price': 1000}],
            'participants': [{'id': 1, 'name': 'P1', 'items': [{'item_id': 1, 'name': 'Item', 'qty': 1, 'price': 1000}]}]
        }
        resp = self.client.post('/api/simpan/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json()['message'], 'kuota 1 hari sudah habis see you besok')

    def test_admin_login_success_and_logout(self):
        """Uji login admin dengan akun admin:superadmin123 dan logout."""
        # 1. Login berhasil
        resp = self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'admin', 'password': 'superadmin123'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['user']['username'], 'admin')

        # 2. Halaman dashboard & create menampilkan status Unlimited untuk admin
        resp_index = self.client.get('/')
        self.assertEqual(resp_index.status_code, 200)
        self.assertEqual(resp_index.context['remaining_quota'], 'Unlimited')
        self.assertTrue(resp_index.context['is_admin'])

        # 3. Admin dapat mereset kuota via /api/admin/reset-kuota/
        resp_reset = self.client.post('/api/admin/reset-kuota/')
        self.assertEqual(resp_reset.status_code, 200)

        # 4. Logout admin
        resp_logout = self.client.post('/api/logout/')
        self.assertEqual(resp_logout.status_code, 200)

        # 5. Setelah logout, kuota kembali ke angka rate limiter biasa
        resp_index_after = self.client.get('/')
        self.assertNotEqual(resp_index_after.context['remaining_quota'], 'Unlimited')

    def test_admin_login_wrong_password_fails(self):
        """Login dengan password salah ditolak dengan HTTP 401."""
        resp = self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'admin', 'password': 'wrongpassword'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()['status'], 'error')

    def test_non_admin_cannot_reset_quota(self):
        """User biasa (tanpa login) ditolak 403 saat mengakses /api/admin/reset-kuota/."""
        resp = self.client.post('/api/admin/reset-kuota/')
        self.assertEqual(resp.status_code, 403)

    def test_homepage_has_two_mode_buttons(self):
        """Halaman utama memuat 2 tombol mode: 'Bagi Rata' dan 'Sendiri-sendiri'."""
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Bagi Rata')
        self.assertContains(resp, 'Sendiri-sendiri')
        self.assertContains(resp, '?mode=bagi-rata')
        self.assertContains(resp, '?mode=sendiri')

    def test_save_equal_split_api_and_view_detail(self):
        """Uji penyimpanan mode Bagi Rata (/api/simpan/) dan tampilan detailnya."""
        cache.clear()
        payload = {
            'split_mode': 'equal',
            'participant_count': 3,
            'participant_names': ['Doni', 'Eka', 'Fani'],
            'bill_info': {
                'restaurant_name': 'Warung Padang Sederhana',
                'transaction_date': '2026-11-06',
                'subtotal': '90000',
                'tax': '9000',
                'service': '1000',
                'discount': '0',
                'other_fees': '0',
                'grand_total': '100000',
            },
            'items': [
                {'id': 1, 'name': 'Nasi Rendang', 'qty': '3', 'price': '30000'}
            ]
        }
        resp = self.client.post('/api/simpan/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['ttl_seconds'], 600)
        token = data['token']

        # Buka halaman detail tagihan
        detail_resp = self.client.get(f'/tagihan/{token}')
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, 'Mode: Bagi Rata')
        self.assertContains(detail_resp, 'Doni')
        self.assertContains(detail_resp, 'Eka')
        self.assertContains(detail_resp, 'Fani')
        self.assertIn('(Bagi Rata)', detail_resp.context['share_text'])

    def test_admin_common_urls_return_404_honeypot(self):
        """URL umum seperti /admin/ dan /admin-dashboard/ mengembalikan 404 palsu untuk menyamarkan admin."""
        resp_admin = self.client.get('/admin/')
        self.assertEqual(resp_admin.status_code, 404)

        resp_dashboard = self.client.get('/admin-dashboard/')
        self.assertEqual(resp_dashboard.status_code, 404)

    def test_admin_dashboard_direct_access_via_secret_url(self):
        """User tanpa login yang mengakses URL rahasia langsung otomatis diautentikasi sebagai admin dan masuk dashboard."""
        admin_url = reverse('splitbill:admin_dashboard')
        resp = self.client.get(admin_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Dashboard Khusus Admin')
        self.assertContains(resp, 'Log Sederhana Aktivitas Pengguna')
        self.assertTemplateUsed(resp, 'splitbill/admin_dashboard.html')

        # Sesi sekarang terotentikasi sebagai admin sehingga kuota menjadi Unlimited
        resp_index = self.client.get('/')
        self.assertEqual(resp_index.status_code, 200)
        self.assertEqual(resp_index.context['remaining_quota'], 'Unlimited')
        self.assertTrue(resp_index.context['is_admin'])

    def test_admin_dashboard_access_granted_for_admin(self):
        """Admin yang login dapat mengakses URL admin spesial dengan status 200."""
        self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'admin', 'password': 'superadmin123'}),
            content_type='application/json'
        )
        admin_url = reverse('splitbill:admin_dashboard')
        resp = self.client.get(admin_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Dashboard Khusus Admin')
        self.assertContains(resp, 'Log Sederhana Aktivitas Pengguna')
        self.assertTemplateUsed(resp, 'splitbill/admin_dashboard.html')

    def test_custom_admin_url_path_from_settings(self):
        """Memastikan ADMIN_URL_PATH terdaftar dengan benar dan reverse URL menunjuk ke slug kustom."""
        from django.conf import settings
        self.assertEqual(settings.ADMIN_URL_PATH, 'portal-rahasia-admin')
        admin_url = reverse('splitbill:admin_dashboard')
        self.assertEqual(admin_url, '/portal-rahasia-admin/')

    def test_admin_reset_all_quota_api(self):
        """Endpoint /api/admin/reset-all-quota/ berhasil mereset seluruh kuota bagi admin."""
        # Anon ditolak
        resp_anon = self.client.post('/api/admin/reset-all-quota/')
        self.assertEqual(resp_anon.status_code, 403)

        # Admin login
        self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'admin', 'password': 'superadmin123'}),
            content_type='application/json'
        )
        resp = self.client.post('/api/admin/reset-all-quota/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')

    def test_admin_reset_user_quota_api(self):
        """Endpoint /api/admin/reset-user-quota/ mereset kuota untuk IP spesifik."""
        # Anon ditolak
        resp_anon = self.client.post('/api/admin/reset-user-quota/', data=json.dumps({'ip': '10.0.0.99'}), content_type='application/json')
        self.assertEqual(resp_anon.status_code, 403)

        # Admin login
        self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'admin', 'password': 'superadmin123'}),
            content_type='application/json'
        )
        resp = self.client.post('/api/admin/reset-user-quota/', data=json.dumps({'ip': '10.0.0.99'}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')
        self.assertEqual(resp.json()['ip'], '10.0.0.99')

    def test_admin_clear_logs_api(self):
        """Endpoint /api/admin/clear-logs/ membersihkan log aktivitas di memory cache."""
        # Anon ditolak
        resp_anon = self.client.post('/api/admin/clear-logs/')
        self.assertEqual(resp_anon.status_code, 403)

        # Admin login
        self.client.post(
            '/api/login/',
            data=json.dumps({'username': 'admin', 'password': 'superadmin123'}),
            content_type='application/json'
        )
        resp = self.client.post('/api/admin/clear-logs/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')




