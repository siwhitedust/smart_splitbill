"""
Modul Pembaca Struk Belanja / Restoran Berbasis Gemini 2.5 Flash API
Smart Splitbill

Menggunakan Google GenAI SDK resmi terbaru (`google-genai`), Pillow, dan Pydantic Structured Outputs.
Menggantikan OCR tradisional (Tesseract & OpenCV) dengan AI Multimodal berakurasi tinggi.
"""

import os
import io
import json
import logging
from typing import List, Optional, Union, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel, Field
# pyrefly: ignore[missing-import]
from google import genai
# pyrefly: ignore[missing-import]
from google.genai import types
# pyrefly: ignore[missing-import]
from google.genai.errors import APIError

# Muat variabel environment dari file .env
load_dotenv()

# Konfigurasi logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Konfigurasi Model & Kredensial
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Model Utama & Rantai Model Cadangan Otomatis (Fallback)
# 1. gemini-2.5-flash: Model utama paling cerdas (kuota 500/hari)
# 2. gemini-2.5-flash-lite & gemini-2.0-flash: Model cadangan hemat kuota (hingga 1.500/hari)
# 3. gemini-3.5-flash-lite: Cadangan modern generasi terbaru
PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_FALLBACK_CHAIN = [
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
]

# Batas waktu timeout per model (dalam detik). Default: 10 detik.
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "10.0"))


def get_model_fallback_chain(preferred_model: Optional[str] = None) -> List[str]:
    """
    Menyusun rantai model AI utama dan model cadangan otomatis (fallback).
    Ketentuan:
    1. Model utama: gemini-2.5-flash (prioritas akurasi)
    2. Model cadangan: gemini-2.5-flash-lite atau gemini-2.0-flash (kuota hingga 1.500/hari)
    3. Cadangan modern: gemini-3.5-flash-lite jika model lama dideprecate/kehabisan kuota
    """
    first_choice = preferred_model or os.getenv("GEMINI_MODEL") or PRIMARY_MODEL
    chain = [first_choice]

    env_fallbacks = os.getenv("GEMINI_FALLBACK_MODELS", "")
    custom_fallbacks = [m.strip() for m in env_fallbacks.split(",") if m.strip()]

    candidates = custom_fallbacks + DEFAULT_FALLBACK_CHAIN
    for m in candidates:
        if m not in chain:
            chain.append(m)

    return chain


# ==============================================================================
# 1. SKEMA DATA STRUKTUR (PYDANTIC STRUCTURED OUTPUT)
# ==============================================================================

class ReceiptItem(BaseModel):
    """Skema untuk setiap item pesanan makanan/minuman."""
    name: str = Field(description="Nama menu makanan atau minuman (bersih dari kode kasir)")
    qty: int = Field(default=1, description="Jumlah porsi/kuantitas yang dipesan (angka bulat integer)")
    unit_price: int = Field(default=0, description="Harga satuan per item dalam Rupiah (integer murni tanpa Rp/titik/koma)")
    total_price: int = Field(default=0, description="Total harga pesanan item ini (qty * unit_price)")


class ReceiptData(BaseModel):
    """
    Skema utama hasil ekstraksi struk belanja / restoran.
    Sesuai kebutuhan kalkulasi proporsional aplikasi Split Bill.
    """
    restaurant_name: Optional[str] = Field(default="", description="Nama restoran/kafe jika tertera pada struk")
    items: List[ReceiptItem] = Field(default_factory=list, description="Daftar menu makanan dan minuman yang dipesan")
    subtotal: int = Field(default=0, description="Total harga semua makanan sebelum pajak dan diskon (integer murni)")
    tax: int = Field(
        default=0,
        description=(
            "Total nominal pajak PB1 / PPN dalam Rupiah yang DITAMBAHKAN di luar harga item. "
            "PENTING: Jika pada struk tertulis bahwa pajak sudah termasuk (Tax Inclusive / Harga termasuk PPN / "
            "Include Tax / Termasuk Pajak) atau jika jumlah harga seluruh item sudah sama dengan grand_total, "
            "maka WAJIB isi nilai tax dengan 0."
        )
    )
    is_tax_inclusive: bool = Field(
        default=False,
        description="True jika pada struk tertulis bahwa pajak sudah termasuk (Tax Inclusive / Harga termasuk PPN / Termasuk Pajak / All prices include tax)."
    )
    service_charge: int = Field(default=0, description="Biaya layanan restoran / ongkir / take away dalam Rupiah (integer, isi 0 jika tidak ada)")
    discount: int = Field(default=0, description="Total potongan harga / promo / voucher sebagai nilai positif (integer, isi 0 jika tidak ada)")
    grand_total: int = Field(default=0, description="Total akhir yang dibayarkan pada struk (integer murni)")


# ==============================================================================
# 2. PROMPT SISTEM & INSTRUKSI AI
# ==============================================================================

SYSTEM_INSTRUCTION = """
Anda adalah asisten AI spesialis ekstraksi struk belanja dan restoran untuk aplikasi pembagi tagihan (Split Bill).
Tugas Anda adalah membaca gambar foto struk kasir dan mengekstrak rincian transaksi secara presisi ke dalam struktur JSON yang diminta.

PEDOMAN PENTING:
1. Daftar Pesanan ('items'):
   - Ekstrak setiap makanan atau minuman yang dibeli.
   - 'name': Nama menu yang bersih (abaikan kode thermal acak seperti 'M', 'H', '4' di ujung nama jika hanya kode internal).
   - 'qty': Jumlah pesanan dalam bilangan bulat (integer). Jika tidak tertulis angka kuantitas, asumsikan bernilai 1.
   - 'unit_price': Harga satuan per item.
   - 'total_price': Total harga untuk item tersebut (qty * unit_price).

2. Komponen Biaya:
   - 'tax': Nominal pajak (PB1, PPN, Tax) yang ditambahkan ke subtotal.
     * ATURAN KHUSUS PAJAK:
       a. Jika pada struk tertulis bahwa pajak sudah termasuk (misalnya 'Tax Inclusive', 'Harga termasuk PPN', 'Include Tax', 'Tax Included', 'Termasuk Pajak', 'All prices include tax', 'Inclusive of Tax/PPN', atau sejenisnya), MAKA isi nilai 'tax' dengan 0, dan set 'is_tax_inclusive': true.
       b. Jika jumlah harga seluruh item (sum of item total_price) sudah sama dengan 'grand_total', MAKA isi nilai 'tax' dengan 0.
       c. Jika pada bagian bawah struk tertulis rincian informasi pajak (misal 'Tax Included Rp 5.000' atau 'PPN 11% Rp 8.000') namun total bayar tidak bertambah karena harga item sudah inklusif, JANGAN masukkan sebagai pajak tambahan; tetap isi 'tax': 0.
       d. Hanya isi 'tax' jika pajak tersebut memang DITAMBAHKAN di luar harga makanan (misal subtotal 50.000 + pajak 5.000 = grand total 55.000). Jika tertulis 'PB 1 10% B.400' atau angka dengan huruf mirip dan memang ditambahkan, tafsirkan dengan benar (misal B.400 = 8400).
       e. Isi 0 jika tidak ada pajak.
   - 'service_charge': Biaya layanan (Service charge, Serv, SC) atau ongkos kirim. Isi 0 jika tidak ada.
   - 'discount': Total diskon, promo, atau voucher. Selalu simpan sebagai angka positif integer. Isi 0 jika tidak ada.
   - 'subtotal': Total harga makanan/minuman sebelum pajak dan diskon.
   - 'grand_total': Total akhir yang harus dibayarkan di struk.

3. Aturan Pembersihan Angka:
   - SEMUA atribut harga (unit_price, total_price, subtotal, tax, service_charge, discount, grand_total) HARUS berupa integer murni.
   - Hapus tulisan "Rp", titik ribuan (.), koma (,), dan spasi. Contoh: 'Rp 25.000' menjadi 25000, '4,000' menjadi 4000.

4. Abaikan Data Tidak Penting:
   - Jangan masukkan nomor telepon, nama jalan/alamat, nama kasir, nomor meja, jam transaksi, metode pembayaran (tunai/kartu), atau uang kembalian ke dalam daftar pesanan 'items'.
"""


# ==============================================================================
# 3. CLIENT GENAI & PEMUATAN GAMBAR DENGAN OPTIMASI JARINGAN & KOMPRESI
# ==============================================================================

import httpx

def get_genai_client(timeout_seconds: Optional[float] = None) -> genai.Client:
    """
    Menginisialisasi client Google GenAI SDK dengan konfigurasi HTTP yang tangguh:
    1. Memaksa koneksi IPv4 (local_address='0.0.0.0') untuk menghindari 'IPv6 blackhole'
       yang sering terjadi pada ISP Indonesia (Indihome/Telkomsel/Biznet/FirstMedia).
    2. Timeout per-model diatur ke 10 detik (default) agar jika model lambat/macet,
       sistem langsung beralih (fallback) ke model cadangan berikutnya secara cepat.
    3. Mendukung proxy (HTTP_PROXY / HTTPS_PROXY) dan custom GEMINI_BASE_URL jika diperlukan.
    """
    api_key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY tidak ditemukan di environment variable atau file .env. "
            "Harap atur GEMINI_API_KEY=AIzaSy... di file .env Anda."
        )

    timeout_val = timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUT_SECONDS

    # Buat transport httpx khusus: Paksa IPv4 dan atur retries transport
    transport = httpx.HTTPTransport(
        local_address="0.0.0.0",  # Memaksa IPv4, melewati masalah timeout IPv6
        retries=2,
    )

    # Konfigurasi timeout per model (10 detik untuk connect, read, write)
    timeout_config = httpx.Timeout(
        connect=timeout_val,  # Batas waktu koneksi TCP & SSL Handshake
        read=timeout_val,     # Batas waktu membaca respons AI (jika lewat, beralih ke model cadangan)
        write=timeout_val,    # Batas waktu mengunggah gambar
        pool=timeout_val      # Batas waktu antrean connection pool
    )

    # Buat instance httpx.Client khusus
    custom_httpx_client = httpx.Client(
        transport=transport,
        timeout=timeout_config,
        trust_env=True,  # Otomatis membaca HTTP_PROXY / HTTPS_PROXY jika pengguna memakai VPN/Proxy
    )

    # Cek apakah pengguna mengonfigurasi custom base URL (misal Cloudflare AI Gateway atau reverse proxy)
    base_url = os.getenv("GEMINI_BASE_URL") or None

    http_options = types.HttpOptions(
        httpx_client=custom_httpx_client,
        base_url=base_url,
        timeout=int(timeout_val * 1000),  # Milidetik untuk types.HttpOptions
    )

    return genai.Client(
        api_key=api_key,
        http_options=http_options
    )


def optimize_image_for_gemini(image: Image.Image, max_dim: int = 1600, quality: int = 85) -> Image.Image:
    """
    Mengompres dan mengubah ukuran gambar sebelum dikirim ke Gemini API:
    - Mengurangi ukuran payload dari ~5MB menjadi ~150KB - 300KB.
    - Mencegah connection / handshake timeout pada koneksi internet yang lambat.
    - Menjaga teks struk tetap sangat tajam dan jelas untuk dibaca model Vision.
    """
    # Pastikan mode RGB (bukan RGBA atau palette)
    if image.mode in ("RGBA", "P", "LA"):
        image = image.convert("RGB")

    w, h = image.size
    # Jika dimensi melebihi batas maksimal, resize proporsional
    if max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        new_w, new_h = int(w * scale), int(h * scale)
        image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Kompresi ringan ke format JPEG di memori
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    return Image.open(buf)


def load_image(image_input: Union[str, Path, bytes, io.BytesIO, Image.Image, Any]) -> Image.Image:
    """Mengubah berbagai format input (file path, bytes, upload file) ke PIL Image yang teroptimasi."""
    try:
        raw_image = None
        if isinstance(image_input, Image.Image):
            raw_image = image_input
        elif isinstance(image_input, (str, Path)):
            file_path = Path(image_input)
            if not file_path.exists():
                raise FileNotFoundError(f"File gambar tidak ditemukan pada path: {file_path}")
            raw_image = Image.open(file_path)
        elif isinstance(image_input, (bytes, bytearray)):
            raw_image = Image.open(io.BytesIO(image_input))
        elif hasattr(image_input, "read"):
            content = image_input.read()
            if hasattr(image_input, "seek"):
                image_input.seek(0)
            raw_image = Image.open(io.BytesIO(content))
        else:
            raise ValueError(f"Format input gambar tidak didukung: {type(image_input)}")

        # Optimasi dan kompres gambar agar ukuran file ringan (< 300KB) saat dikirim ke Gemini
        return optimize_image_for_gemini(raw_image)

    except Exception as e:
        logger.error(f"Gagal memuat atau mengompres gambar: {e}")
        raise ValueError(f"File yang diberikan bukan gambar yang valid atau format rusak: {e}")


# ==============================================================================
# 4. FUNGSI UTAMA EKSTRAKSI STRUK DENGAN GEMINI FLASH
# ==============================================================================

def scan_receipt_gemini(
    image_input: Union[str, Path, bytes, io.BytesIO, Image.Image, Any],
    model: Optional[str] = None,
    enable_fallback: bool = True,
    timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Mengekstrak informasi struk belanja/restoran menggunakan Gemini Flash API.
    Sesuai ketentuan spesifikasi:
    1. temperature=0.0: Mematikan sifat 'kreatif' AI agar membaca teks apa adanya secara kaku & konsisten.
    2. response_schema=ReceiptData (Pydantic Structured Outputs): Menjamin 100% format JSON valid.
    3. Model Cadangan Otomatis (Fallback): Otomatis berpindah dari model utama (gemini-2.5-flash)
       ke model cadangan (gemini-3.5-flash-lite, gemini-3.1-flash-lite, gemini-3.5-flash)
       saat kuota harian habis (429), server Google sedang sibuk (503), atau waktu pemrosesan melebihi 10 detik.
    4. Timeout Per-Model: Batas waktu maksimal 10 detik per model panggilan API. Jika lebih dari 10 detik,
       langsung fallback otomatis ke model cadangan berikutnya.

    :param image_input: File path, bytes gambar, atau objek file upload
    :param model: Model pilihan yang ingin diprioritaskan (opsional)
    :param enable_fallback: Apakah otomatis berpindah ke model cadangan jika model utama gagal
    :param timeout_seconds: Batas waktu timeout per-model dalam detik (default: 10.0 detik)
    :return: Dictionary berisi data transaksi yang rapi dan terstruktur
    """
    try:
        # 1. Muat dan validasi gambar dengan Pillow (terkompresi & teroptimasi)
        pil_image = load_image(image_input)

        timeout_val = timeout_seconds if timeout_seconds is not None else DEFAULT_TIMEOUT_SECONDS

        # 2. Inisialisasi client Gemini dengan konfigurasi timeout per-model
        client = get_genai_client(timeout_seconds=timeout_val)

        # 3. Tentukan rantai model yang akan dicoba (Primary -> Fallbacks)
        models_to_try = get_model_fallback_chain(model) if enable_fallback else [model or PRIMARY_MODEL]
        
        response = None
        successful_model = None
        last_error = None
        fallback_history = []

        # 4. Jalankan inferensi dengan fallback otomatis antar-model
        for idx, current_model in enumerate(models_to_try):
            is_fallback = (idx > 0)
            prefix = f"[Fallback Cadangan #{idx}] " if is_fallback else ""
            logger.info(f"{prefix}Mengirim gambar struk ke model '{current_model}' (timeout={int(timeout_val)}s, temperature=0.0)...")

            try:
                # Panggilan Gemini API dengan Structured Outputs & temperature 0.0 serta timeout per-model
                resp = client.models.generate_content(
                    model=current_model,
                    contents=[
                        pil_image,
                        "Baca dan ekstrak seluruh data transaksi dari foto struk ini ke format JSON terstruktur."
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        response_schema=ReceiptData,
                        temperature=0.0,  # Wajib 0.0: Matikan kreatifitas, baca teks kaku & konsisten
                        http_options=types.HttpOptions(
                            timeout=int(timeout_val * 1000)
                        ),
                    ),
                )
                if resp and resp.text:
                    response = resp
                    successful_model = current_model
                    logger.info(f"Berhasil mengekstrak data struk menggunakan model '{current_model}'.")
                    break
            except Exception as err:
                last_error = err
                err_str = str(err)
                err_lower = err_str.lower()

                # Deteksi tipe kendala untuk log penjelasan yang informatif
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    reason = "Kuota harian habis / Rate limit (429 RESOURCE_EXHAUSTED)"
                elif "503" in err_str or "UNAVAILABLE" in err_str:
                    reason = "Server Google sedang sibuk / High demand (503 UNAVAILABLE)"
                elif "404" in err_str or "NOT_FOUND" in err_str:
                    reason = "Model tidak tersedia / Dialihkan ke generasi terbaru (404 NOT_FOUND)"
                elif any(k in err_lower for k in ["timeout", "timed out", "time out", "deadline"]):
                    reason = f"Waktu pemrosesan melebihi {int(timeout_val)} detik (Timeout)"
                else:
                    reason = err_str.split("\n")[0][:120]

                fallback_history.append({"model": current_model, "error": reason})
                logger.warning(
                    f"Model '{current_model}' belum berhasil ({reason}). "
                    f"Otomatis beralih ke model cadangan berikutnya..."
                )

        if not response or not response.text:
            failures_summary = "; ".join([f"{item['model']}: {item['error']}" for item in fallback_history])
            raise RuntimeError(
                f"Semua model (utama & cadangan) gagal memproses struk. Rincian kegagalan: {failures_summary}"
            )

        # 5. Parse hasil teks JSON menjadi dictionary Python
        extracted_dict = json.loads(response.text)

        # 6. Validasi logika perhitungan dasar (pencegahan inkonsistensi)
        items = extracted_dict.get("items", [])
        calculated_subtotal = sum(it.get("total_price", 0) for it in items)
        
        # Jika AI mengembalikan subtotal 0 tetapi ada item, gunakan hitungan item
        if extracted_dict.get("subtotal", 0) == 0 and calculated_subtotal > 0:
            extracted_dict["subtotal"] = calculated_subtotal

        # Jika grand_total 0, hitung otomatis
        if extracted_dict.get("grand_total", 0) == 0:
            st = extracted_dict.get("subtotal", 0)
            tx = extracted_dict.get("tax", 0)
            sc = extracted_dict.get("service_charge", 0)
            dc = extracted_dict.get("discount", 0)
            extracted_dict["grand_total"] = max(0, st + tx + sc - dc)

        # 7. Penanganan Pajak Sudah Termasuk (Tax Inclusive) atau Item Total == Grand Total:
        # Jika pada struk tertulis pajak sudah termasuk (Tax Inclusive / Harga termasuk PPN)
        # atau jika jumlah harga seluruh item sudah sama dengan grand_total, maka isi nilai tax dengan 0.
        grand_total = extracted_dict.get("grand_total", 0)
        is_tax_inclusive = bool(extracted_dict.get("is_tax_inclusive", False))

        if is_tax_inclusive or (calculated_subtotal > 0 and calculated_subtotal == grand_total):
            logger.info(
                f"Pajak diset ke 0: is_tax_inclusive={is_tax_inclusive}, "
                f"calculated_subtotal={calculated_subtotal}, grand_total={grand_total}"
            )
            extracted_dict["tax"] = 0
            extracted_dict["is_tax_inclusive"] = True

        return {
            "status": "success",
            "model_used": successful_model,
            "fallback_history": fallback_history,
            "data": extracted_dict,
        }

    except FileNotFoundError as fnf_err:
        logger.error(f"File tidak ditemukan: {fnf_err}")
        return {
            "status": "error",
            "message": str(fnf_err),
        }
    except APIError as api_err:
        logger.error(f"Gemini API Error: {api_err}")
        return {
            "status": "error",
            "message": f"Koneksi ke Gemini API gagal: {api_err.message if hasattr(api_err, 'message') else str(api_err)}",
        }
    except Exception as err:
        logger.error(f"Kesalahan tidak terduga saat memproses struk: {err}", exc_info=True)
        return {
            "status": "error",
            "message": f"Gagal membaca struk: {str(err)}",
        }


# ==============================================================================
# CLI / TESTING STANDALONE
# ==============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 65)
    print(" Smart Splitbill - Gemini Flash Receipt Scanner (google-genai)")
    print("=" * 65)

    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        print(f"\n[+] Membaca gambar dari: {test_file}")
        res = scan_receipt_gemini(test_file)
        print("\nHasil Ekstraksi JSON:")
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print("\n[i] Penggunaan CLI: python gemini_receipt_ocr.py <path_ke_foto_struk.jpg>\n")
        # Contoh jika ada struk default dalam direktori kerja
        sample_path = "/home/whitedust/.gemini/antigravity/brain/00f1c7a6-5eb9-42e8-a5c2-f8d8a3bfa815/.user_uploaded/media_1793780686865_9702b62f.jpg"
        if os.path.exists(sample_path):
            print(f"[+] Menjalankan uji coba dengan struk sampel: {sample_path}")
            res = scan_receipt_gemini(sample_path)
            print("\nHasil Ekstraksi JSON:")
            print(json.dumps(res, indent=2, ensure_ascii=False))
