# Smart Splitbill 🧾⚡
**Aplikasi Web Pembagi Tagihan Pintar Berbasis AI Vision (Gemini Flash) & Django Cache (TTL 10 Menit)**

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.1-green)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![AI Engine](https://img.shields.io/badge/AI%20OCR-Google%20Gemini%20Flash-orange)](https://aistudio.google.com/)

Smart Splitbill adalah aplikasi web *privacy-first* untuk membagi tagihan makan/belanja secara adil, cepat, dan presisi. Cukup unggah atau foto struk kasir, AI akan membaca seluruh rincian transaksi otomatis, lalu Anda dapat membagi pesanan ke masing-masing orang secara interaktif (Drag & Drop atau Sentuhan Mobile). Pajak, biaya layanan, dan diskon dihitung proporsional tanpa ada selisih pembulatan (menggunakan metode **Largest Remainder**).

---

## ✨ Fitur Unggulan

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

## 📁 Struktur Direktori Proyek

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

## 🚀 Panduan Instalasi & Menjalankan Aplikasi

### 1. Kebutuhan Sistem
- **Python:** 3.10, 3.11, atau 3.12
- **Google Gemini API Key:** Dapatkan gratis di [Google AI Studio](https://aistudio.google.com/)

---

### 2. Kloning Repositori & Virtual Environment

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

---

### 3. Konfigurasi Environment Variables

Salin template konfigurasi `.env.example` menjadi `.env`:

```bash
cp .env.example .env
```

Buka file `.env` dan masukkan kunci API Gemini Anda:
```ini
GEMINI_API_KEY=AIzaSy_masukkan_api_key_anda_di_sini
```

---

### 4. Migrasi Database & Jalankan Server

```bash
# Migrasi database SQLite lokal (untuk auth dan logging)
python manage.py migrate

# Jalankan server pengembangan
python manage.py runserver 8000
```

Buka browser Anda di: **`http://127.0.0.1:8000/`**

---

### 5. (Opsional) Membuka Akses Publik via Cloudflare Tunnel

Jika Anda ingin orang lain/teman dapat membuka web ini langsung dari server lokal laptop Anda secara aman dan gratis via HTTPS:

1. Unduh `cloudflared` sesuai sistem operasi Anda.
2. Di terminal baru, jalankan:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
3. Salin URL publik `https://...trycloudflare.com` yang dihasilkan dan bagikan ke teman Anda!

---

## 🧪 Menjalankan Pengujian (Testing)

Proyek ini telah dilengkapi dengan 52 unit test otomatis yang mencakup pengujian kalkulasi finansial, pembulatan pecahan, penanganan kesalahan API, proteksi upload file, hingga masa kedaluwarsa sesi:

```bash
source venv/bin/activate
python manage.py test splitbill.tests
```

---

## 🤝 Panduan Kontribusi

Kontribusi dari komunitas sangat diterima! Silakan baca panduan di [CONTRIBUTING.md](CONTRIBUTING.md) untuk informasi cara melaporkan bug, menyarankan fitur, atau mengirimkan *Pull Request*.

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah lisensi **MIT License** — silakan baca file [LICENSE](LICENSE) untuk detail lengkap.

Dibuat dengan ❤️ oleh [siwhitedust](https://github.com/siwhitedust).
