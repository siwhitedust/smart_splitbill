<div align="center">

# Smart Splitbill 🧾⚡
**Smart Bill Splitting Web Application Powered by AI Vision (Gemini Flash) & Django Cache (10-Minute TTL)**  
*Aplikasi Web Pembagi Tagihan Pintar Berbasis AI Vision (Gemini Flash) & Django Cache (TTL 10 Menit)*

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.1-green)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![AI Engine](https://img.shields.io/badge/AI%20OCR-Google%20Gemini%20Flash-orange)](https://aistudio.google.com/)

---

**Pilih Bahasa / Select Language:**  
**[ 🇬🇧 English ](#-english)** &nbsp;•&nbsp; **[ 🇮🇩 Bahasa Indonesia ](#-bahasa-indonesia)**

---

</div>

<br>

---

## 🇬🇧 English

Smart Splitbill is a **privacy-first** web application designed to split dining and shopping bills fairly, quickly, and precisely. Simply take a photo or upload a receipt, and Google Gemini AI extracts transaction details automatically. Then, interactively assign items to participants (via Drag & Drop on desktop or touch on mobile). Taxes, service charges, discounts, and tips are proportionally distributed with zero rounding discrepancy using the **Largest Remainder** algorithm.

---

### ✨ Key Features

1. **Advanced AI Vision OCR (Google Gemini Flash):**
   - Powered by official Google GenAI SDK (`gemini-2.5-flash`) with Pydantic Structured Outputs.
   - Automatic extraction: restaurant name, date, itemized list, unit prices, quantity, subtotal, tax, discount, service charge, and grand total.
   - **Smart Fallback Engine:** Automatically switches to alternative models (`gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`) if the primary model encounters rate limits or server overload.

2. **Privacy & Security First:**
   - **Zero Relational Bill Storage:** Bill records are never stored in permanent database tables (SQLite/PostgreSQL).
   - **10-Minute TTL (600s):** Bills are kept temporarily in Django In-Memory Cache. Once expired, data is automatically purged.
   - **Immediate Receipt Deletion:** Uploaded images are processed in memory / temporary storage and **immediately deleted** right after extraction (`try...finally`).
   - **Read-Only Shareable URLs:** Bills are shared via randomized cryptographic tokens (e.g., `/tagihan/x8kPo9QmT2vN7aBc`) that can only read data, preventing unauthorized tampering.
   - **Rate Limiting:** Built-in daily quota limiter per IP + Session to avoid API overuse.

3. **Precise Financial Calculations (Zero Rounding Discrepancy):**
   - High-precision `Decimal` arithmetic (eliminates floating-point calculation errors).
   - Proportional distribution for tax, service charge, discounts, and tips based on each person's actual orders.
   - Uses the **Largest Remainder** method for Rupiah rounding, guaranteeing that **the sum of everyone's share equals 100% of the receipt's Grand Total**.
   - Supports fractional servings (e.g., 0.5 portion for shared dishes).

4. **Modern UI/UX: Simple, Neutral Superglass:**
   - Clean aesthetic featuring Superglass styling (translucent glassmorphism, subtle borders, high contrast).
   - Intuitive Wizard (Upload Receipt -> Review OCR -> Split Items -> Share URL).
   - Interactive item assignment (Drag & Drop on desktop + quick `+ Add` button for touchscreens).
   - One-click copy buttons for WhatsApp and Telegram bill breakdown messages.

5. **Local Hosting & Deployment Ready:**
   - Run securely from your own laptop over HTTPS using **Cloudflare Tunnel (`cloudflared`)** with no port forwarding or public IP required.
   - Production ready for cloud hosting (Render, Railway, VPS) with **Gunicorn** and **WhiteNoise**.

---

### 📁 Project Directory Structure

```text
smart_splitbill/
├── config/                     # Django Main Configuration
│   ├── settings.py             # App settings, cache, middleware, security
│   ├── urls.py                 # Global URL routing
│   ├── asgi.py
│   └── wsgi.py
├── splitbill/                  # Core Splitbill App
│   ├── services/               # Business Service Layer (Clean Architecture)
│   │   ├── ocr_service.py      # Gemini Flash AI OCR integration & error handling
│   │   ├── calculation_service.py # Proportional & Largest Remainder calculations
│   │   ├── cache_service.py    # 600s TTL cache management
│   │   └── rate_limiter.py     # Daily quota rate limiter per IP & session
│   ├── static/splitbill/       # Frontend Assets (Superglass CSS, Vanilla JS, Logo)
│   ├── templates/splitbill/    # Django HTML Templates
│   │   ├── base.html           # Base layout & navbar
│   │   ├── index.html          # Homepage & active bill history
│   │   ├── create.html         # Bill creation wizard & splitting interface
│   │   ├── detail.html         # Public read-only shared bill page
│   │   └── expired.html        # Friendly 404 page for expired bills
│   ├── tests/                  # Comprehensive Automated Tests (52 Test Cases)
│   ├── error_views.py          # Custom 404 & 500 error handlers
│   ├── utils.py                # Helpers for token generation, Rupiah formatting
│   ├── validators.py           # Upload & payload validation
│   └── views.py                # HTTP Controllers & JSON API endpoints
├── gemini_receipt_ocr.py       # Receipt extraction engine via Google GenAI SDK
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── manage.py                   # Django CLI Runner
└── README.md                   # Project Documentation
```

---

### 🚀 Installation & Getting Started

#### 1. System Requirements
- **Python:** 3.10, 3.11, or 3.12
- **Google Gemini API Key:** Obtain free of charge from [Google AI Studio](https://aistudio.google.com/)

#### 2. Clone Repository & Setup Virtual Environment

```bash
# 1. Clone repository
git clone https://github.com/siwhitedust/smart_splitbill.git
cd smart_splitbill

# 2. Create virtual environment
python3 -m venv venv

# 3. Activate virtual environment
# On Linux / macOS:
source venv/bin/activate
# On Windows (PowerShell):
# .\venv\Scripts\Activate.ps1

# 4. Install all dependencies
pip install -r requirements.txt
```

#### 3. Configure Environment Variables

Copy the `.env.example` template to `.env`:

```bash
cp .env.example .env
```

Open `.env` and set your Gemini API Key:
```ini
GEMINI_API_KEY=AIzaSy_your_gemini_api_key_here
```

#### 4. Run Migrations & Start Development Server

```bash
# Migrate local SQLite database (used for admin logs & sessions)
python manage.py migrate

# Start development server
python manage.py runserver 8000
```

Open your browser at: **`http://127.0.0.1:8000/`**

#### 5. (Optional) Expose Publicly via Cloudflare Tunnel

To share your locally running web server with friends over HTTPS without port forwarding:

1. Install `cloudflared` on your system.
2. In a separate terminal, run:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
3. Copy and share the generated `https://...trycloudflare.com` URL!

---

### 🧪 Running Automated Tests

The project includes 52 automated unit test cases covering calculations, fractional portions, API error handling, upload security, and TTL expiration:

```bash
source venv/bin/activate
python manage.py test splitbill.tests
```

---

<br>

---

## 🇮🇩 Bahasa Indonesia

Smart Splitbill adalah aplikasi web *privacy-first* untuk membagi tagihan makan/belanja secara adil, cepat, dan presisi. Cukup unggah atau foto struk kasir, AI akan membaca seluruh rincian transaksi otomatis, lalu Anda dapat membagi pesanan ke masing-masing orang secara interaktif (Drag & Drop di desktop atau sentuhan di ponsel). Pajak, biaya layanan, dan diskon dihitung proporsional tanpa ada selisih pembulatan (menggunakan metode **Largest Remainder**).

---

### ✨ Fitur Unggulan

1. **AI Vision OCR Canggih (Google Gemini Flash):**
   - Menggunakan model `gemini-2.5-flash` resmi dari Google GenAI SDK dengan *Structured Outputs* (Pydantic).
   - Ekstraksi otomatis: nama restoran, tanggal, daftar item, harga satuan, kuantitas, subtotal, pajak, diskon, service charge, hingga grand total.
   - **Multi-Model Fallback:** Jika kuota model utama habis atau server Google sedang sibuk, aplikasi otomatis beralih ke model cadangan secara cerdas.

2. **Privasi & Keamanan Tinggi (Privacy-First):**
   - **Tanpa Database Tagihan Permanen:** Data tagihan sama sekali tidak disimpan ke tabel database permanen (SQLite/PostgreSQL).
   - **TTL 10 Menit (600 Detik):** Seluruh data tagihan disimpan sementara di Django Cache (*In-Memory*). Setelah 10 menit, data otomatis hangus dan musnah dari server.
   - **Foto Struk Dihapus Seketika:** Gambar struk diproses di memori/temporary file dan **langsung dihapus** begitu ekstraksi selesai (`try...finally`). Tidak ada file foto yang tertinggal di server.
   - **Read-Only Shared URL:** Tagihan dibagikan lewat tautan unik acak (contoh: `/tagihan/x8kPo9QmT2vN7aBc`) yang hanya bisa dibaca dan tidak bisa dimanipulasi orang lain.
   - **Rate Limiting:** Proteksi kuota analisis struk per hari per IP + Session untuk mencegah penyalahgunaan API.

3. **Kalkulasi Finansial Presisi (Zero-Rounding-Discrepancy):**
   - Menggunakan tipe data `Decimal` presisi tinggi (mencegah bug *floating point*).
   - Pajak, Service Charge, dan Diskon didistribusikan secara proporsional sesuai nominal pesanan tiap individu.
   - Menggunakan metode matematika **Largest Remainder** untuk pembulatan Rupiah yang deterministik, menjamin **jumlah iuran tiap orang 100% tepat sama dengan Grand Total pada struk**.
   - Mendukung porsi pecahan (misal 0.5 jika 1 menu dibagi berdua).

4. **UI/UX Modern: Simple, Neutral Superglass:**
   - Desain minimalis bernuansa *Superglass* (translucent glassmorphism, border tipis, kontras tinggi).
   - Wizard intuitif (Upload Foto -> Review OCR -> Bagi Pesanan -> Simpan & Berbagi).
   - Antarmuka pembagian pesanan interaktif (Drag & Drop di desktop + tombol `+ Tambah` cepat untuk layar sentuh ponsel).
   - Tombol instan: **Salin Tautan** dan **Salin Rincian untuk WhatsApp / Telegram**.

5. **Akses Publik Mudah & Deployment Ready:**
   - Siap dijalankan dari laptop sendiri menggunakan **Cloudflare Tunnel (`cloudflared`)** tanpa perlu port forwarding atau IP publik.
   - Siap dideploy ke cloud provider (Render, Railway, VPS) dengan **Gunicorn** dan **WhiteNoise**.

---

### 📁 Struktur Direktori Proyek

```text
smart_splitbill/
├── config/                     # Pengaturan Utama Django
│   ├── settings.py             # Konfigurasi App, Cache, Middleware, Security
│   ├── urls.py                 # Routing URL global
│   ├── asgi.py
│   └── wsgi.py
├── splitbill/                  # Aplikasi Splitbill
│   ├── services/               # Lapisan Layanan Bisnis (Clean Architecture)
│   │   ├── ocr_service.py      # Integrasi Gemini Flash AI OCR & Error Handling
│   │   ├── calculation_service.py # Logika Proporsional & Largest Remainder
│   │   ├── cache_service.py    # Manajemen TTL Cache 600 detik
│   │   └── rate_limiter.py     # Pembatas kuota harian per IP & Sesi
│   ├── static/splitbill/       # Aset Frontend (CSS Superglass, Vanilla JS, Logo)
│   ├── templates/splitbill/    # Template Tampilan HTML Django
│   │   ├── base.html           # Layout dasar & Navbar
│   │   ├── index.html          # Beranda & riwayat aktif
│   │   ├── create.html         # Wizard pembuatan & pembagian tagihan
│   │   ├── detail.html         # Halaman tagihan publik (read-only)
│   │   └── expired.html        # Halaman jika tagihan telah kedaluwarsa
│   ├── tests/                  # Unit Test Komprehensif (52 Test Cases)
│   ├── error_views.py          # Custom handler 404 & 500
│   ├── utils.py                # Helper format rupiah & token
│   ├── validators.py           # Validasi upload & payload
│   └── views.py                # Controller HTTP & Endpoint JSON
├── gemini_receipt_ocr.py       # Engine ekstraksi struk via Google GenAI SDK
├── requirements.txt            # Dependensi Python
├── .env.example                # Template Environment Variables
├── manage.py                   # CLI Runner Django
└── README.md                   # Dokumentasi Proyek
```

---

### 🚀 Panduan Instalasi & Menjalankan Aplikasi

#### 1. Kebutuhan Sistem
- **Python:** 3.10, 3.11, atau 3.12
- **Google Gemini API Key:** Dapatkan gratis di [Google AI Studio](https://aistudio.google.com/)

#### 2. Kloning Repositori & Virtual Environment

```bash
# 1. Kloning repositori
git clone https://github.com/siwhitedust/smart_splitbill.git
cd smart_splitbill

# 2. Buat virtual environment
python3 -m venv venv

# 3. Aktifkan virtual environment
# Di Linux / macOS:
source venv/bin/activate
# Di Windows (PowerShell):
# .\venv\Scripts\Activate.ps1

# 4. Pasang seluruh dependensi
pip install -r requirements.txt
```

#### 3. Konfigurasi Environment Variables

Salin template konfigurasi `.env.example` menjadi `.env`:

```bash
cp .env.example .env
```

Buka file `.env` dan masukkan kunci API Gemini Anda:
```ini
GEMINI_API_KEY=AIzaSy_masukkan_api_key_anda_di_sini
```

#### 4. Migrasi Database & Jalankan Server

```bash
# Migrasi database SQLite lokal (untuk auth dan logging)
python manage.py migrate

# Jalankan server pengembangan
python manage.py runserver 8000
```

Buka browser Anda di: **`http://127.0.0.1:8000/`**

#### 5. (Opsional) Membuka Akses Publik via Cloudflare Tunnel

Jika Anda ingin orang lain/teman dapat membuka web ini langsung dari server lokal laptop Anda secara aman dan gratis via HTTPS:

1. Unduh `cloudflared` sesuai sistem operasi Anda.
2. Di terminal baru, jalankan:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
3. Salin URL publik `https://...trycloudflare.com` yang dihasilkan dan bagikan ke teman Anda!

---

### 🧪 Menjalankan Pengujian (Testing)

Proyek ini telah dilengkapi dengan 52 unit test otomatis yang mencakup pengujian kalkulasi finansial, pembulatan pecahan, penanganan kesalahan API, proteksi upload file, hingga masa kedaluwarsa sesi:

```bash
source venv/bin/activate
python manage.py test splitbill.tests
```

---

## 🤝 Contributing / Panduan Kontribusi

Contributions are always welcome! / Kontribusi dari komunitas sangat diterima!  
Please read / Silakan baca panduan lengkap di: **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

## 📄 License / Lisensi

Proyek ini dilisensikan di bawah lisensi **MIT License** — silakan baca file [LICENSE](LICENSE) untuk detail lengkap.

Created with ❤️ by [siwhitedust](https://github.com/siwhitedust).
