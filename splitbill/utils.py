"""
Utilitas bantuan untuk Smart Splitbill.
Format Rupiah, pembuatan token kriptografis, deteksi IP, dan parsing desimal.
"""

import re
import secrets
import string
from decimal import Decimal, InvalidOperation
from datetime import datetime
import zoneinfo
from django.conf import settings

JAKARTA_TZ = zoneinfo.ZoneInfo(getattr(settings, 'TIME_ZONE', 'Asia/Jakarta'))


def get_jakarta_now() -> datetime:
    """Mengembalikan datetime saat ini dalam zona waktu Asia/Jakarta."""
    return datetime.now(JAKARTA_TZ)


def generate_bill_token(length: int = 16) -> str:
    """
    Menghasilkan token URL acak kriptografis yang aman dan sulit ditebak.
    Contoh: 'x8kPo9QmT2vN7aBc'
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def format_rupiah(value, with_prefix: bool = True) -> str:
    """
    Memformat angka atau Decimal menjadi format mata uang Rupiah.
    Contoh: 25000 -> 'Rp25.000'
    """
    if value is None:
        value = 0
    try:
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        value = Decimal('0')

    # Jika bernilai bulat
    if value == value.to_integral():
        formatted_num = f"{int(value):,}".replace(",", ".")
    else:
        # Jika ada pecahan desimal
        int_part = int(value)
        dec_part = abs(value - int_part)
        dec_str = f"{dec_part:.2f}".split('.')[1]
        formatted_num = f"{int_part:,}".replace(",", ".") + f",{dec_str}"

    return f"Rp{formatted_num}" if with_prefix else formatted_num


def parse_decimal(value, default: str = '0') -> Decimal:
    """
    Mengonversi input teks/angka ke Decimal dengan toleransi format Indonesia.
    Mengabaikan karakter selain angka, titik, koma, minus, dan menangani pemisah ribuan titik maupun koma.
    """
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    s = str(value).strip()
    if not s:
        return Decimal(default)

    # Hilangkan spasi di antara digit pemisah (misal '19, 000' -> '19,000')
    s = re.sub(r'([.,])\s+([0-9])', r'\1\2', s)

    # Hapus simbol non-numerik selain minus, koma, dan titik
    s = re.sub(r'[^\d.,\-]', '', s)

    # Tangani format Indonesia seperti "25.000,50" atau "25.000" atau "25,000"
    if '.' in s and ',' in s:
        # Titik adalah ribuan, koma adalah desimal
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s and '.' not in s:
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) == 3:
            # Format koma ribuan mesin kasir POS (misal 4,000 atau 92,400)
            s = s.replace(',', '')
        elif len(parts) > 2:
            # Format koma ribuan jamak (misal 1,000,000)
            s = s.replace(',', '')
        else:
            # Format koma desimal pecahan (misal 1,5 atau 0,75)
            s = s.replace(',', '.')
    elif '.' in s and ',' not in s:
        parts = s.split('.')
        if len(parts) == 2 and len(parts[1]) == 3:
            # 1 titik dan 3 digit setelahnya (misal 50.000, 67.000, 8.400) -> ribuan
            s = s.replace('.', '')
        elif len(parts) > 2:
            # Format titik ribuan jamak (misal 1.000.000)
            s = s.replace('.', '')

    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def get_client_ip(request) -> str:
    """
    Mendapatkan alamat IP asli klien dari request headers.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip
