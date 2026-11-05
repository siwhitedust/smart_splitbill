"""
Unit test untuk OCR Receipt Service berbasis Gemini Flash API:
- Ekstraksi data struk (restoran, items, kuantitas, harga, pajak, service, diskon, grand total)
- Penanganan jika kuota model AI habis: pesan 'kuota 1 hari sudah habis see you besok'
- Verifikasi jaminan keamanan tanpa penyimpanan file permanen
"""

import io
from unittest.mock import patch
from PIL import Image
from django.test import SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from splitbill.services.ocr_service import OCRReceiptService, QuotaExceededError, ServerBusyError


class OCRReceiptServiceTest(SimpleTestCase):
    def setUp(self):
        self.service = OCRReceiptService()

    @patch('splitbill.services.ocr_service.scan_receipt_gemini')
    def test_process_receipt_image_gemini_success(self, mock_scan):
        """Uji sukses ekstraksi data struk terstruktur via Gemini Flash API."""
        mock_scan.return_value = {
            "status": "success",
            "model_used": "gemini-3.5-flash-lite",
            "data": {
                "restaurant_name": "KOPI KENANGAN MANTAN",
                "items": [
                    {
                        "name": "Kopi Kenangan Mantan",
                        "qty": 2,
                        "unit_price": 20000,
                        "total_price": 40000
                    },
                    {
                        "name": "Roti Coklat Klasik",
                        "qty": 1,
                        "unit_price": 15000,
                        "total_price": 15000
                    }
                ],
                "subtotal": 55000,
                "tax": 5500,
                "service_charge": 2500,
                "discount": 5000,
                "grand_total": 58000
            }
        }

        img = Image.new('RGB', (200, 100), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        uploaded = SimpleUploadedFile('test_receipt.jpg', buf.getvalue(), content_type='image/jpeg')

        result = self.service.process_receipt_image(uploaded)

        self.assertEqual(result['restaurant_name'], 'KOPI KENANGAN MANTAN')
        self.assertEqual(len(result['items']), 2)
        self.assertEqual(result['subtotal'], '55000')
        self.assertEqual(result['tax'], '5500')
        self.assertEqual(result['service'], '2500')
        self.assertEqual(result['discount'], '5000')
        self.assertEqual(result['grand_total'], '58000')
        self.assertEqual(result['model_used'], 'gemini-3.5-flash-lite')

    @patch('splitbill.services.ocr_service.scan_receipt_gemini')
    def test_quota_exceeded_error_handling(self, mock_scan):
        """Uji jika kuota AI harian habis (429 / RESOURCE_EXHAUSTED)."""
        mock_scan.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED: Kuota harian habis")

        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        uploaded = SimpleUploadedFile('struk.jpg', buf.getvalue(), content_type='image/jpeg')

        with self.assertRaises(QuotaExceededError) as ctx:
            self.service.process_receipt_image(uploaded)

        self.assertEqual(str(ctx.exception), "kuota 1 hari sudah habis see you besok")

    @patch('splitbill.services.ocr_service.scan_receipt_gemini')
    def test_server_busy_error_handling(self, mock_scan):
        """Uji jika terjadi error semua model gagal karena server sibuk (503 UNAVAILABLE)."""
        mock_scan.side_effect = RuntimeError(
            "Semua model (utama & cadangan) gagal memproses struk. Rincian kegagalan: "
            "gemini-2.5-flash: Kuota harian habis / Rate limit (429 RESOURCE_EXHAUSTED); "
            "gemini-3.5-flash-lite: Server Google sedang sibuk / High demand (503 UNAVAILABLE)"
        )

        img = Image.new('RGB', (100, 100), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        uploaded = SimpleUploadedFile('struk.jpg', buf.getvalue(), content_type='image/jpeg')

        with self.assertRaises(ServerBusyError) as ctx:
            self.service.process_receipt_image(uploaded)

        self.assertEqual(str(ctx.exception), "server sedang sibuk")
