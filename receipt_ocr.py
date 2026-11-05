"""
Modul OCR Pembaca Struk Belanja / Restoran
Smart Splitbill

Menggunakan OpenCV, Pillow (PIL), dan PyTesseract untuk:
1. Pembersihan dan pra-pemrosesan citra struk (Resize 2x CUBIC, Grayscale, Gaussian Blur, Adaptive Thresholding).
2. Ekstraksi teks baris per baris dengan PyTesseract (ind+eng, --oem 3 --psm 6).
3. Pemisahan otomatis (parsing) data pesanan, biaya tambahan, dan diskon ke format JSON/Dictionary.
"""

import os
import re
import sys
import json
import logging
from typing import Dict, Any, List, Optional
import cv2
import numpy as np
from PIL import Image
import pytesseract

# Konfigurasi logging sederhana
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Konfigurasi path binary Tesseract jika belum ada di PATH sistem
# Otomatis mendeteksi environment venv pada Linux atau instalasi standar Windows
DEFAULT_TESSERACT_PATHS = [
    os.path.join(os.path.dirname(__file__), "venv", "bin", "tesseract"),
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]
for t_path in DEFAULT_TESSERACT_PATHS:
    if os.path.exists(t_path):
        pytesseract.pytesseract.tesseract_cmd = t_path
        break


# ==============================================================================
# 1. TAHAP PEMBERSIHAN & PRA-PEMROSESAN GAMBAR (OPENCV & PILLOW)
# ==============================================================================

def preprocess_image(image_input: Any) -> Image.Image:
    """
    Membersihkan gambar struk menggunakan OpenCV:
    1. Resize 2x lipat dengan interpolasi CUBIC agar teks kecil lebih tajam.
    2. Ubah warna menjadi grayscale (skala abu-abu).
    3. Haluskan bintik kasar (noise) dengan Gaussian Blur.
    4. Terapkan Adaptive Thresholding untuk menajamkan teks hitam-putih dan
       menghilangkan bayangan lipatan kertas / kamera HP.
    5. Konversi hasil akhir ke format Pillow Image.

    :param image_input: Jalur file gambar (str) atau byte array gambar
    :return: Objek PIL Image yang telah diolah dan siap dibaca Tesseract
    """
    try:
        # Baca gambar dari path file atau buffer bytes
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"File gambar tidak ditemukan: {image_input}")
            img = cv2.imread(image_input)
        elif isinstance(image_input, (bytes, bytearray)):
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_input, np.ndarray):
            img = image_input
        else:
            raise ValueError("Format input gambar tidak didukung (harus path string atau bytes).")

        if img is None:
            raise ValueError("Gambar gagal dimuat atau format file rusak.")

        # Langkah 1: Perbesar ukuran gambar (resize) 2x lipat menggunakan interpolasi CUBIC
        # Membantu karakter dot-matrix atau font kasir kecil terbaca lebih jelas
        h, w = img.shape[:2]
        resized = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

        # Langkah 2: Ubah warna gambar menjadi abu-abu (grayscale)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        # Langkah 3: Haluskan bintik kasar (noise) menggunakan Gaussian Blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Langkah 4: Adaptive Thresholding (Gaussian C) untuk menajamkan teks
        # menjadi hitam-putih bersih dan menghilangkan bayangan foto kamera HP
        # Ukuran block size (31) dan konstanta C (10) optimal untuk struk kasir
        thresholded = cv2.adaptiveThreshold(
            blurred,
            maxValue=255,
            adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            thresholdType=cv2.THRESH_BINARY,
            blockSize=31,
            C=10
        )

        # Langkah 5: Konversi hasil akhir dari OpenCV (numpy array) ke format Pillow Image
        pil_image = Image.fromarray(thresholded)
        return pil_image

    except Exception as e:
        logger.error(f"Error pada tahap pra-pemrosesan gambar: {e}")
        raise


# ==============================================================================
# 2. TAHAP EKSTRAKSI TEKS (PYTESSERACT)
# ==============================================================================

def extract_text(pil_image: Image.Image, lang: str = "ind+eng") -> str:
    """
    Mengekstrak teks dari gambar menggunakan PyTesseract.
    Konfigurasi:
    - --oem 3: Default OCR Engine Mode (LSTM Neural Network modern).
    - --psm 6: Assume a single uniform block of text (membaca per baris dari kiri
               ke kanan sehingga nama menu dan harga tetap sejajar di satu baris).

    :param pil_image: Objek Pillow Image
    :param lang: Bahasa OCR ('ind+eng' untuk Indonesia dan Inggris)
    :return: String teks mentah hasil pembacaan
    """
    try:
        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(pil_image, lang=lang, config=custom_config)
        return text
    except Exception as e:
        logger.error(f"Error saat mengeksekusi Tesseract OCR: {e}")
        # Coba fallback ke bahasa Inggris saja jika data pack bahasa Indonesia belum terpasang
        try:
            logger.info("Mencoba fallback Tesseract dengan bahasa 'eng'...")
            return pytesseract.image_to_string(pil_image, lang="eng", config=r"--oem 3 --psm 6")
        except Exception as e_fallback:
            raise RuntimeError(f"Gagal mengekstrak teks dengan Tesseract: {e_fallback}")


# ==============================================================================
# 3. TAHAP PEMISAHAN DATA OTOMATIS (REGEX & PARSING KE JSON)
# ==============================================================================

def clean_price_to_int(price_str: str) -> int:
    """
    Membersihkan format angka harga:
    - Menghapus 'Rp', titik ribuan, koma desimal, spasi, atau simbol lainnya.
    - Mengonversi menjadi angka bulat (integer).
    Contoh: 'Rp 25.000' -> 25000, '4,000' -> 4000, 'B.400' -> 8400.
    """
    if not price_str:
        return 0
    # Tangani salah baca huruf 'B' menjadi angka 8 di awal nominal (misal B.400 -> 8400)
    normalized = re.sub(r'^[Bb]([.,]\d+)', r'8\1', price_str.strip())
    digits_only = re.sub(r"[^0-9]", "", normalized)
    return int(digits_only) if digits_only else 0


def parse_receipt_text(raw_text: str) -> Dict[str, Any]:
    """
    Membedah teks hasil OCR per baris menggunakan Regex dan memisahkan ke dalam:
    a. Daftar pesanan (nama menu, qty, harga satuan, total harga).
    b. Biaya tambahan (pajak/PB1/PPN, biaya layanan/service charge, ongkir).
    c. Potongan harga (diskon, promo, voucher).
    d. Mengabaikan teks non-transaksi (nama toko, alamat, kasir, tanggal, dll).

    :param raw_text: Teks mentah dari Tesseract OCR
    :return: Dictionary terstruktur siap dikonversi ke JSON
    """
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

    # Daftar kata kunci teks yang harus diabaikan (header, footer, info kasir, total ringkasan)
    ignore_patterns = [
        r"\b(selamat datang|terima kasih|thank you|visit|wifi|password)\b",
        r"\b(cashier|kasir|waiter|pelayan|table|meja|guest|tamu|pax|bill no|order id)\b",
        r"\b(telp|phone|fax|[pf]\.?\s*\d{5,}|jl\.|jalan|raya|lantai|gedung)\b",
        r"\b(tunai|cash|kembali|change|debit|kredit|qris|gopay|ovo|dana|shopeepay)\b",
        r"\b(subtotal|sub-total|grand\s*total|total\s*bayar|total\s*tagihan|total\s*akhir|amount\s*due)\b",
        r"\b(senin|selasa|rabu|kamis|jumat|sabtu|minggu|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\b\d{1,2}[:.]\d{2}(?:[:.]\d{2})?\b",  # Baris waktu / jam
        r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",     # Baris tanggal di awal
        r"^[=\-_*#\s\.:]+$",                     # Garis strip pembatas
    ]

    # Pola Regex untuk mendeteksi kategori biaya tambahan & potongan harga
    tax_pattern = re.compile(r"\b(pajak|tax|pb\s*1|ppn|pjk|gov[\s\-]?tax)\b", re.IGNORECASE)
    service_pattern = re.compile(r"\b(service|layanan|serv|sc|biaya\s*layanan)\b", re.IGNORECASE)
    delivery_pattern = re.compile(r"\b(ongkir|delivery|ongkos\s*kirim|pengantaran|take\s*away)\b", re.IGNORECASE)
    discount_pattern = re.compile(r"\b(diskon|discount|disc|promo|potongan|voucher|hemat)\b", re.IGNORECASE)

    # Regex untuk mendeteksi nominal harga di ujung baris (contoh: 25.000, Rp25.000, 4,000, 19000)
    price_regex = re.compile(r"(?:Rp\.?\s*)?([0-9Bb]{1,3}(?:[.,][0-9]{3})+|[0-9]{4,})[^\d]*$", re.IGNORECASE)

    items: List[Dict[str, Any]] = []
    fees: Dict[str, int] = {
        "pajak": 0,
        "service_charge": 0,
        "ongkos_kirim": 0,
    }
    discounts: Dict[str, int] = {
        "diskon": 0,
    }

    item_id = 1

    for line in lines:
        line_clean = line.strip()

        # 1. Periksa apakah baris harus diabaikan (nama toko, alamat, kasir, waktu, dll)
        if any(re.search(pat, line_clean, re.IGNORECASE) for pat in ignore_patterns):
            continue

        # Normalisasi karakter 'B' jika angka awal pajak terbaca B.400 -> 8.400
        line_normalized = re.sub(r"\b[Bb]\.([0-9]{3})\b", r"8.\1", line_clean)

        # Cari nominal harga di ujung baris
        price_match = price_regex.search(line_normalized)
        if not price_match:
            continue

        raw_price_str = price_match.group(1)
        amount = clean_price_to_int(raw_price_str)

        # Abaikan angka yang terlalu kecil (< Rp 500) atau nomor telepon/tanggal (> Rp 5.000.000)
        if amount < 500 or amount > 5000000:
            continue

        # Ambil teks nama item/keterangan sebelum nominal harga
        text_before_price = line_normalized[:price_match.start()].strip()

        # 2. Cek apakah baris ini adalah Diskon / Potongan Harga
        if discount_pattern.search(text_before_price):
            discounts["diskon"] += amount
            continue

        # 3. Cek apakah baris ini adalah Biaya Tambahan
        if tax_pattern.search(text_before_price):
            fees["pajak"] += amount
            continue
        if service_pattern.search(text_before_price):
            fees["service_charge"] += amount
            continue
        if delivery_pattern.search(text_before_price):
            fees["ongkos_kirim"] += amount
            continue

        # 4. Jika bukan biaya tambahan atau diskon, perlakukan sebagai Daftar Pesanan (Menu)
        # Ekstrak kuantitas (qty) di awal nama jika tersedia, misalnya:
        # "1 Cheezy Freezy", "2x Nasi Goreng", atau karakter misread "i" / "l" / "|"
        qty_match = re.match(r"^([0-9]+|[il\|])\s*[xX*]?\s+(.*)", text_before_price)
        if qty_match:
            qty_raw = qty_match.group(1)
            qty = 1 if qty_raw.lower() in ["i", "l", "|"] else int(qty_raw)
            item_name = qty_match.group(2).strip()
        else:
            qty = 1
            item_name = text_before_price.strip()

        # Pembersihan teks nama menu dari simbol noise di awal/akhir
        item_name = re.sub(r"^[^\w]+|[^\w]+$", "", item_name).strip()
        # Hilangkan kode kasir pendek di ujung menu (misal 'M' atau '4')
        item_name = re.sub(r"\s+[A-Za-z0-9]{1,2}$", "", item_name).strip()

        # Koreksi typo umum OCR pada minuman
        item_name = re.sub(r"\b(lemon|lychee|green|milk|es|ice|sweet|hot|thai)\s+tes\b", r"\1 Tea", item_name, flags=re.IGNORECASE)
        item_name = re.sub(r"\blegon\s+tea\b", "Lemon Tea", item_name, flags=re.IGNORECASE)

        # Validasi: nama menu harus memiliki minimal 3 karakter dan mengandung huruf
        if len(item_name) >= 3 and any(c.isalpha() for c in item_name):
            # Harga satuan dihitung dari total harga dibagi kuantitas
            unit_price = amount // qty if qty > 0 else amount
            items.append({
                "id": item_id,
                "nama_menu": item_name,
                "qty": qty,
                "harga_satuan": unit_price,
                "total_harga": amount,
            })
            item_id += 1

    # Perhitungan total ringkasan untuk validasi pembagian tagihan
    subtotal_pesanan = sum(item["total_harga"] for item in items)
    total_biaya_tambahan = sum(fees.values())
    total_potongan = sum(discounts.values())
    grand_total = subtotal_pesanan + total_biaya_tambahan - total_potongan

    return {
        "status": "success",
        "data": {
            "pesanan": items,
            "biaya_tambahan": fees,
            "potongan_harga": discounts,
            "ringkasan": {
                "subtotal_pesanan": subtotal_pesanan,
                "total_biaya_tambahan": total_biaya_tambahan,
                "total_potongan": total_potongan,
                "grand_total": grand_total,
            },
        },
    }


# ==============================================================================
# 4. FUNGSI UTAMA (INTEGRASI END-TO-END DENGAN TRY-EXCEPT)
# ==============================================================================

def read_receipt(image_input: Any) -> Dict[str, Any]:
    """
    Fungsi utama untuk memproses struk dari gambar hingga menjadi data JSON:
    1. Membaca & membersihkan gambar (OpenCV -> Pillow).
    2. Ekstraksi teks baris per baris (Tesseract OCR).
    3. Parsing teks terstruktur (Regex).
    4. Dilengkapi penanganan error (try-except) jika gambar gagal dibaca.

    :param image_input: Jalur file gambar (str) atau byte array gambar
    :return: Dictionary hasil pembacaan struk
    """
    try:
        # 1. Pembersihan & Pra-pemrosesan citra
        pil_image = preprocess_image(image_input)

        # 2. Ekstraksi teks menggunakan Tesseract
        raw_text = extract_text(pil_image)
        if not raw_text.strip():
            return {
                "status": "warning",
                "message": "Gambar berhasil diproses, namun tidak ada teks yang terdeteksi pada struk.",
                "data": {
                    "pesanan": [],
                    "biaya_tambahan": {"pajak": 0, "service_charge": 0, "ongkos_kirim": 0},
                    "potongan_harga": {"diskon": 0},
                    "ringkasan": {"subtotal_pesanan": 0, "total_biaya_tambahan": 0, "total_potongan": 0, "grand_total": 0},
                },
                "raw_text": "",
            }

        # 3. Parsing data otomatis ke format terstruktur
        parsed_result = parse_receipt_text(raw_text)
        parsed_result["raw_text"] = raw_text.strip()
        return parsed_result

    except FileNotFoundError as fnf_err:
        logger.error(f"File tidak ditemukan: {fnf_err}")
        return {
            "status": "error",
            "message": f"File gambar tidak ditemukan: {str(fnf_err)}",
        }
    except Exception as err:
        logger.error(f"Gagal memproses struk: {err}", exc_info=True)
        return {
            "status": "error",
            "message": f"Terjadi kesalahan saat memproses gambar struk: {str(err)}",
        }


# ==============================================================================
# CONTOH PENGGUNAAN & PENGUJIAN (CLI / STANDALONE)
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print(" Smart Splitbill - OCR & Parser Struk Belanja / Makanan")
    print("=" * 60)

    # Jika pengguna memberikan path gambar via argumen CLI:
    # python receipt_ocr.py <path_gambar>
    if len(sys.argv) > 1:
        target_image = sys.argv[1]
        print(f"\n[+] Memproses gambar dari: {target_image}")
        result = read_receipt(target_image)
    else:
        # Contoh simulasi menggunakan teks struk bawaan jika tidak ada file yang diberikan
        print("\n[i] Tidak ada argumen path gambar. Menjalankan simulasi parsing teks struk...\n")
        dummy_receipt = """
        WARUNG MAKAN NUSANTARA
        Jl. Kemang Raya No. 88 Jakarta Selatan
        Telp: 021-7193776
        Kasir: Marra    Meja: 32
        Tanggal: 04-11-2026 14:30:15
        ========================================
        1 Cheezy Freezy           Rp 25.000
        1 Red Bull                Rp 25.000
        1 Lemon Tea                  11.000
        1 Cappucinno Frozen          19.000
        ----------------------------------------
        Subtotal                     80.000
        PB 1 10% (Pajak)              8.400
        Serv 5% (Service Charge)      4.000
        Ongkos Kirim                  5.000
        Diskon Promo Voucher         10.000
        ========================================
        Grand Total                  87.400
        Tunai                       100.000
        Kembali                      12.600
        ========================================
        Terima Kasih Atas Kunjungan Anda!
        Password Wifi: warung123
        """
        result = parse_receipt_text(dummy_receipt)

    print("\nHasil Ekstraksi JSON:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

