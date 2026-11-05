"""
FastAPI Server untuk Pembaca Struk Belanja / Restoran
Smart Splitbill API

Endpoint:
- POST /api/v1/ocr/scan  : Menerima upload file gambar struk (multipart/form-data)
- GET  /health           : Health check endpoint
- GET  /docs             : Swagger UI dokumentasi interaktif API
"""

import io
import logging
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Impor pipeline ekstraksi dan skema data Gemini Flash API
from gemini_receipt_ocr import scan_receipt_gemini, ReceiptData, ReceiptItem

logger = logging.getLogger(__name__)

# ==============================================================================
# INISIALISASI APLIKASI FASTAPI
# ==============================================================================
app = FastAPI(
    title="Smart Splitbill - Gemini Flash Receipt API",
    version="2.0.0",
    description=(
        "API microservice berbasis FastAPI untuk memproses dan mengekstrak foto struk "
        "belanja/restoran menggunakan Google GenAI SDK (Gemini 2.5 Flash) ke format JSON terstruktur."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Konfigurasi CORS agar API dapat diakses dari frontend web (Django, React, Vue) maupun mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Batasan ukuran file maksimal (5 MB)
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}


# ==============================================================================
# SKEMA RESPONSE (PYDANTIC MODELS)
# ==============================================================================

class OCRScanResponse(BaseModel):
    status: str = Field(..., example="success")
    message: Optional[str] = Field(None, description="Pesan informasi atau error jika gagal")
    data: Optional[ReceiptData] = Field(None, description="Hasil ekstraksi transaksi terstruktur dari Gemini")


# ==============================================================================
# ENDPOINT API
# ==============================================================================

@app.get("/", tags=["General"])
def root():
    """Halaman pengantar dan tautan ke dokumentasi Swagger."""
    return {
        "app": "Smart Splitbill OCR API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["General"])
def health_check():
    """Endpoint untuk mengecek status kesehatan server API."""
    return {"status": "ok", "service": "ocr-splitbill"}


@app.post(
    "/api/v1/ocr/scan",
    response_model=OCRScanResponse,
    status_code=status.HTTP_200_OK,
    tags=["OCR Receipt"],
    summary="Unggah dan Ekstraksi Foto Struk",
    description=(
        "Menerima file gambar struk belanja/restoran (JPG, PNG, WEBP), "
        "memproses pembersihan gambar dengan OpenCV, mengekstrak teks dengan PyTesseract, "
        "dan memisahkan menu pesanan, biaya tambahan, serta diskon ke dalam format JSON terstruktur."
    ),
)
async def scan_receipt(
    file: UploadFile = File(..., description="File foto struk (maksimal 5 MB)")
):
    """
    Endpoint utama penerima file upload gambar struk.
    """
    # 1. Validasi Tipe Konten File (MIME Type)
    content_type = file.content_type.lower() if file.content_type else ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Tipe file '{content_type}' tidak diizinkan. "
                "Harap unggah file gambar berformat JPG, JPEG, PNG, atau WEBP."
            ),
        )

    # 2. Baca isi file ke memori (bytes)
    try:
        image_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gagal membaca file gambar yang diunggah: {str(e)}",
        )

    # 3. Validasi Ukuran File (Maksimal 5MB)
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File yang diunggah kosong (0 bytes).",
        )
    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Ukuran file melebihi batas maksimal ({MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB).",
        )

    # 4. Jalankan Pipeline Ekstraksi Gemini 2.5 Flash
    try:
        result = scan_receipt_gemini(image_bytes)
    except Exception as e:
        logger.error(f"Error tidak terduga saat pemrosesan struk: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan internal pada pemrosesan Gemini: {str(e)}",
        )

    # 5. Cek status hasil ekstraksi
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.get("message", "Gagal memproses struk."),
        )

    return result


# ==============================================================================
# ENTRY POINT UNTUK MENJALANKAN SERVER SECARA MANDIRI
# ==============================================================================

if __name__ == "__main__":
    # Jalankan server FastAPI pada port 8000 (atau port lain)
    # Akses Swagger UI di: http://127.0.0.1:8000/docs
    uvicorn.run("api_fastapi:app", host="0.0.0.0", port=8000, reload=True)

