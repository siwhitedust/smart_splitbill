"""
Service OCR dan ekstraksi data struk belanja / restoran.
Smart Splitbill

Menggunakan Google GenAI SDK resmi (Gemini Flash API) dengan Structured Outputs Pydantic.
OCR lokal (Tesseract & OpenCV) telah dihapus sepenuhnya sesuai permintaan karena
hasil pembacaannya tidak akurat/berantakan.
"""

import os
import logging
from typing import Dict, Any
from splitbill.utils import format_rupiah
# pyrefly: ignore[missing-import]
from gemini_receipt_ocr import scan_receipt_gemini

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Exception khusus saat kuota AI habis."""
    pass


class ServerBusyError(Exception):
    """Exception khusus saat server AI Google sedang sibuk / overloaded (503)."""
    pass


class OCRReceiptService:
    """
    Ekstraksi data struk belanja murni berbasis Gemini Flash API
    dengan Fallback Model Otomatis dan Structured Output Pydantic (temperature=0.0).
    """

    def process_receipt_image(self, uploaded_file) -> Dict[str, Any]:
        """
        Menerima file gambar yang diunggah, memprosesnya dengan Gemini Flash API (google-genai),
        mengekstrak data transaksi, dan memetakan hasilnya ke format struktur data Split Bill.
        Jika kuota habis (baik model utama maupun model cadangan), memicu pesan:
        'kuota 1 hari sudah habis see you besok'
        Jika server Google sedang sibuk (503 / high demand), memicu pesan:
        'server sedang sibuk'
        """
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY tidak dikonfigurasi di file .env. "
                "Harap atur GEMINI_API_KEY Anda terlebih dahulu."
            )

        # Pastikan pointer file berada di awal jika berupa stream
        if hasattr(uploaded_file, "seek"):
            try:
                uploaded_file.seek(0)
            except Exception:
                pass

        try:
            gemini_res = scan_receipt_gemini(uploaded_file)
        except Exception as e:
            err_msg = str(e)
            err_lower = err_msg.lower()
            if any(k in err_lower for k in ["503", "unavailable", "server google sedang sibuk", "high demand", "server sedang sibuk", "semua model", "timeout", "timed out", "time out", "deadline"]):
                raise ServerBusyError("server sedang sibuk")
            if any(k in err_lower for k in ["429", "resource_exhausted", "quota", "kuota"]):
                raise QuotaExceededError("kuota 1 hari sudah habis see you besok")
            raise

        if gemini_res.get("status") == "error":
            err_msg = gemini_res.get("message", "")
            err_lower = err_msg.lower()
            if any(k in err_lower for k in ["503", "unavailable", "server google sedang sibuk", "high demand", "server sedang sibuk", "semua model", "timeout", "timed out", "time out", "deadline"]):
                raise ServerBusyError("server sedang sibuk")
            if any(k in err_lower for k in ["429", "resource_exhausted", "quota", "kuota"]):
                raise QuotaExceededError("kuota 1 hari sudah habis see you besok")
            raise RuntimeError(err_msg or "Gagal memproses struk dengan Gemini API.")

        d = gemini_res["data"]
        model_used = gemini_res.get("model_used", "Gemini")
        items = []
        for idx, it in enumerate(d.get("items", [])):
            q = str(it.get("qty", 1))
            p = str(it.get("unit_price", 0))
            tot = str(it.get("total_price", int(q) * int(p)))
            items.append({
                "id": idx + 1,
                "name": it.get("name", ""),
                "qty": q,
                "price": p,
                "unit_price": int(p),
                "price_formatted": format_rupiah(p),
                "subtotal": tot,
                "total_price": int(tot),
                "subtotal_formatted": format_rupiah(tot),
                "confidence": "high",
            })

        logger.info(f"Sukses mengekstrak data struk menggunakan {model_used} (temperature=0.0).")

        # Logika Pajak: Jika tertulis pajak sudah termasuk (Tax Inclusive / Harga termasuk PPN)
        # atau jika jumlah harga seluruh item sudah sama dengan grand_total, maka isi nilai tax dengan 0.
        total_items_price = sum(int(it.get("qty", 1)) * int(it.get("unit_price", 0)) for it in d.get("items", []))
        grand_total_int = int(d.get("grand_total", 0) or 0)
        is_tax_inc = bool(d.get("is_tax_inclusive", False))
        raw_tax = int(d.get("tax", 0) or 0)

        if is_tax_inc or (total_items_price > 0 and total_items_price == grand_total_int):
            final_tax = 0
            is_tax_inc = True
        else:
            final_tax = raw_tax

        return {
            "restaurant_name": d.get("restaurant_name") or "Restoran / Kafe",
            "transaction_date": "",
            "items": items,
            "subtotal": str(d.get("subtotal", 0)),
            "tax": str(final_tax),
            "is_tax_inclusive": is_tax_inc,
            "service": str(d.get("service_charge", 0)),
            "service_charge": d.get("service_charge", 0),
            "discount": str(d.get("discount", 0)),
            "other_fees": "0",
            "grand_total": str(d.get("grand_total", 0)),
            "raw_text": f"Extracted via {model_used} ({len(items)} items)",
            "model_used": model_used,
        }


ocr_receipt_service = OCRReceiptService()
