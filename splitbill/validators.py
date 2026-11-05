"""
Validator untuk file unggahan struk, data transaksi, dan pembagian pesanan.
"""

import os
from typing import Tuple, List, Dict, Any
from django.conf import settings
from splitbill.utils import parse_decimal

ALLOWED_MIME_TYPES = getattr(settings, 'ALLOWED_MIME_TYPES', ['image/jpeg', 'image/png', 'image/webp'])
ALLOWED_EXTENSIONS = getattr(settings, 'ALLOWED_EXTENSIONS', ['.jpg', '.jpeg', '.png', '.webp'])
MAX_UPLOAD_SIZE = getattr(settings, 'MAX_UPLOAD_SIZE_BYTES', 5 * 1024 * 1024)


def validate_receipt_file(uploaded_file) -> Tuple[bool, str]:
    """
    Validasi keamanan file gambar struk:
    - Keberadaan file
    - Ukuran maksimum (<= 5MB)
    - Ekstensi file yang diizinkan
    - MIME Content-Type yang valid
    """
    if not uploaded_file:
        return False, "File gambar struk tidak ditemukan."

    # Periksa ukuran file
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        max_mb = MAX_UPLOAD_SIZE // (1024 * 1024)
        return False, f"Ukuran file terlalu besar. Maksimum ukuran adalah {max_mb} MB."

    # Periksa ekstensi file
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Format ekstensi file '{ext}' tidak didukung. Harap unggah file JPG, JPEG, PNG, atau WEBP."

    # Periksa MIME type
    content_type = getattr(uploaded_file, 'content_type', '')
    if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
        return False, f"Tipe file '{content_type}' tidak diizinkan. Harap unggah gambar yang valid."

    return True, ""


def validate_bill_submission(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validasi data formulir splitbill sebelum disimpan ke Cache:
    - Restoran
    - Daftar Item
    - Daftar Peserta
    """
    errors = []

    if not isinstance(payload, dict):
        return False, ["Payload data tagihan tidak valid."]

    bill_info = payload.get('bill_info', {})
    items = payload.get('items', [])
    participants = payload.get('participants', [])

    # 1. Validasi Restoran
    resto_name = str(bill_info.get('restaurant_name', '')).strip()
    if not resto_name:
        errors.append("Nama restoran/kafe tidak boleh kosong.")

    # 2. Validasi Items
    if not items or not isinstance(items, list):
        errors.append("Struk harus memiliki minimal 1 item pesanan.")
    else:
        for idx, item in enumerate(items):
            it_name = str(item.get('name', '')).strip()
            if not it_name:
                errors.append(f"Nama item #{idx + 1} tidak boleh kosong.")

            qty = parse_decimal(item.get('qty', 0))
            if qty <= 0:
                errors.append(f"Kuantitas item '{it_name}' harus lebih dari 0.")

            price = parse_decimal(item.get('price', 0))
            if price < 0:
                errors.append(f"Harga item '{it_name}' tidak boleh negatif.")

    # 3. Validasi Peserta
    if not participants or not isinstance(participants, list):
        errors.append("Harus ada minimal satu orang peserta untuk membagi tagihan.")
    else:
        for p_idx, p in enumerate(participants):
            p_name = str(p.get('name', '')).strip()
            if not p_name:
                errors.append(f"Nama peserta #{p_idx + 1} tidak boleh kosong.")

    return len(errors) == 0, errors

