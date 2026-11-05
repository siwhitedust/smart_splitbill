# Smart Splitbill 🧾⚡
**Aplikasi Web Pembagi Tagihan Pintar Berbasis OCR & Django Cache (TTL 10 Menit)**

Smart Splitbill adalah aplikasi web yang memungkinkan pengguna memotret struk pembayaran, mengekstrak rincian transaksi otomatis menggunakan OCR lokal (Tesseract & OpenCV), membagikan pesanan ke beberapa orang secara interaktif (Drag & Drop + Touch-friendly), serta menghitung proporsi pajak, biaya layanan, dan diskon secara adil dan presisi tanpa selisih pembulatan (menggunakan metode Largest Remainder).

---

## ✨ Fitur Unggulan

1. **OCR Struk Kasir Lokal (Tanpa Biaya API Eksternal):**
   - Menggunakan Tesseract OCR dengan bahasa Indonesia (`ind`) dan Inggris (`eng`).
   - Pra-pemrosesan gambar berbasis OpenCV (Grayscale, Denoising, Otsu Thresholding) untuk mempertajam struk yang buram atau minim kontras.
   - Deteksi otomatis nama restoran, tanggal, daftar item, kuantitas, harga, subtotal, pajak, biaya layanan, diskon, dan grand total.

2. **Privasi & Keamanan Tinggi:**
   - **Tanpa Database Relasional:** Tidak menyimpan tagihan ke database permanen seperti SQLite, PostgreSQL, atau MySQL.
   - **Penyimpanan Sementara (TTL 600 Detik):** Seluruh tagihan disimpan di Django Cache selama tepat 10 menit (600 detik). Setelah itu, data otomatis kedaluwarsa dan dihapus.
   - **Foto Struk Segera Dihapus:** File foto struk diproses di memori/temporary file dan **selalu dihapus** seketika proses OCR selesai (`try...finally`). Foto tidak pernah disimpan ke folder media atau static.
   - **URL Tagihan Unik & Read-Only:** Tagihan dibagikan melalui token kriptografis acak (contoh: `/tagihan/x8kPo9QmT2vN7aBc`). URL hanya dapat membaca tagihan dan tidak dapat digunakan untuk memanipulasi data.
   - **Rate Limiting Backend:** Maksimal 5 kali analisis struk per hari per IP + Session (direset tengah malam WIB sesuai zona waktu `Asia/Jakarta`).

3. **Kalkulasi Bisnis Presisi (Zero-Rounding-Discrepancy):**
   - Menggunakan tipe data `Decimal` (bukan float) untuk mencegah masalah floating point.
   - Pembagian proporsional untuk Pajak, Service Charge, Diskon, dan Biaya Tambahan.
   - Metode **Largest Remainder** untuk pembulatan Rupiah yang deterministik sehingga jumlah total tiap peserta **selalu 100% sama dengan Grand Total pada struk**.
   - Mendukung porsi pecahan (misal 0.5 atau 1.5).

4. **UI/UX Modern: Simple, Neutral Superglass:**
   - Desain minimalis bernuansa Superglass (translucent glassmorphism, border tipis, kontras tinggi).
   - Wizard intuitif (Upload -> Review OCR -> Bagi Pesanan -> Review -> URL Berbagi).
   - Modal Pembagian Pesanan 2 Kolom (desktop) & Fullscreen Vertikal (mobile).
   - Drag & Drop HTML5 interaktif PLUS tombol alternatif `+ Tambah` yang nyaman untuk layar sentuh ponsel.
   - Tombol instan *Salin Rincian untuk WhatsApp / Telegram*.

---

## 📁 Struktur Direktori Proyek

```text
smart_splitbill/
├── config/                     # Konfigurasi Proyek Django
│   ├── settings.py             # Pengaturan Django (Cache, Session, Security, Timezone)
│   ├── urls.py                 # Routing URL utama
│   ├── asgi.py
│   └── wsgi.py
├── splitbill/                  # Aplikasi Utama Splitbill
│   ├── services/               # Layer Service Terpisah (Clean Architecture)
│   │   ├── cache_service.py    # Service Cache TTL 600s (LocMemCache / Redis)
│   │   ├── ocr_service.py      # Ekstraksi Tesseract OCR & OpenCV Preprocessing
│   │   ├── calculation_service.py # Logika Proporsional & Largest Remainder Rupiah
│   │   └── rate_limiter.py     # Pembatas kuota 5x/hari (Asia/Jakarta)
│   ├── static/splitbill/       # Aset Frontend
│   │   ├── css/style.css       # Design System Simple Neutral Superglass
│   │   └── js/
│   │       ├── app.js          # Utilitas global (Toast, Countdown, Copy, Format Rupiah)
│   │       └── splitbill.js    # Interaktivitas Wizard, Drag & Drop, In-Memory State
│   ├── templates/splitbill/    # Template Django HTML
│   │   ├── base.html           # Layout dasar & Navbar
│   │   ├── index.html          # Dashboard riwayat aktif sesi
│   │   ├── create.html         # Wizard pembuatan splitbill terpadu
│   │   ├── detail.html         # Shared bill read-only (/tagihan/<token>)
│   │   └── expired.html        # Tampilan ramah bila tagihan kedaluwarsa (404)
│   ├── tests/                  # Unit Test Komprehensif
│   │   ├── test_calculation.py # Uji kalkulasi & pembulatan
│   │   ├── test_cache_service.py # Uji TTL & sesi cache
│   │   ├── test_rate_limiter.py# Uji batas 5x/hari
│   │   ├── test_ocr_service.py # Uji parsing teks & pembersihan file
│   │   └── test_views_security.py # Uji endpoint & keamanan
│   ├── error_views.py          # Custom error handler (404, 500)
│   ├── utils.py                # Helper format Rupiah, token, IP
│   ├── validators.py           # Validasi file & payload
│   ├── views.py                # Controller HTTP & API JSON
│   └── urls.py                 # URL route aplikasi splitbill
├── venv/                       # Virtual Environment Python
├── .env.example                # Contoh environment variable
├── requirements.txt            # Dependensi Python
├── manage.py                   # Runner CLI Django
└── README.md                   # Dokumentasi
```

---

## 🚀 Panduan Instalasi & Menjalankan Aplikasi

### 1. Kebutuhan Sistem
- Python 3.10, 3.11, atau 3.12
- Tesseract OCR (dengan paket bahasa Indonesia `ind` dan Inggris `eng`)

#### Memasang Tesseract di Sistem (Jika belum terpasang):
- **Ubuntu/Debian:**
  ```bash
  sudo apt-get update
  sudo apt-get install tesseract-ocr tesseract-ocr-ind tesseract-ocr-eng libgl1
  ```
- **Fedora/RHEL:**
  ```bash
  sudo dnf install tesseract tesseract-langpack-ind tesseract-langpack-eng
  ```
- *(Catatan untuk environment ini: wrapper lokal Tesseract telah disediakan di dalam `venv/bin/tesseract`)*.

---

### 2. Membuat Virtual Environment & Instalasi Dependency

```bash
# Buat virtual environment
python3 -m venv venv

# Aktifkan virtual environment
source venv/bin/activate

# Instal seluruh dependensi Python
pip install -r requirements.txt
```

---

### 3. Konfigurasi Environment (Opsional)

Salin `.env.example` menjadi `.env` jika ingin mengubah pengaturan:
```bash
cp .env.example .env
```

Isi variabel konfigurasi utama:
- `DJANGO_DEBUG`: `True` untuk development, `False` untuk production.
- `SPLITBILL_TTL_SECONDS`: Masa simpan tagihan (default `600` detik = 10 menit).
- `RATE_LIMIT_DAILY_MAX`: Kuota analisis struk harian (default `5`).
- `DJANGO_REDIS_URL`: URL Redis jika production (contoh: `redis://127.0.0.1:6379/1`). Bila kosong, aplikasi otomatis menggunakan `LocMemCache`.

---

### 4. Menjalankan Server Pengembangan

```bash
source venv/bin/activate
python manage.py runserver 8000
```
Buka peramban (browser) di: **`http://127.0.0.1:8000/`**

---

## 🧪 Menjalankan Pengujian (Testing)

Proyek ini dilengkapi dengan 20 test cases komprehensif:
- Pengujian kalkulasi 1 peserta & banyak peserta
- Pengujian porsi pecahan (0.5 porsi)
- Pengujian pembulatan Largest Remainder Rupiah
- Pengujian kedaluwarsa TTL cache
- Pengujian rate limiter 5x/hari
- Pengujian proteksi upload file berbahaya (.exe/.txt) & ukuran berlebih (>5MB)
- Pengujian OCR end-to-end dengan pembersihan foto seketika

Untuk menjalankan seluruh pengujian:
```bash
source venv/bin/activate
python manage.py test splitbill.tests
```

---

## 📖 Cara Menggunakan Aplikasi

1. **Halaman Beranda (`/`):**
   - Melihat daftar tagihan aktif yang pernah disimpan selama 10 menit terakhir.
   - Setiap kartu menampilkan restoran, jumlah orang, total tagihan, dan sisa waktu aktif.
   - Klik tombol **Buat Splitbill Baru**.

2. **Langkah 1 — Foto Struk:**
   - Gunakan tombol kamera ponsel atau unggah foto struk dari galeri.
   - Tekan **Baca Struk Pembayaran**.
   - *(Atau pilih opsi input manual jika tidak memiliki foto struk).*

3. **Langkah 2 — Periksa Hasil OCR:**
   - Review data restoran, item menu, harga satuan, dan kuantitas.
   - Edit, tambah, atau hapus item jika ada yang perlu disesuaikan.
   - Isi komponen pajak, biaya layanan, diskon, dan grand total.
   - Jika terdapat selisih antara item dan grand total struk, sistem akan memberikan notifikasi peringatan.
   - Klik **Lanjutkan ke Pembagian Pesanan**.

4. **Langkah 3 — Pembagian Pesanan:**
   - Klik **+ Tambah Orang**.
   - Di modal pembagian, seret menu pesanan dari kolom kiri ke kanan via Drag & Drop, atau gunakan tombol **+ Tambah** (sangat nyaman di layar sentuh ponsel).
   - Tentukan porsi (mendukung porsi pecahan misal 0.5 jika 1 menu dimakan berdua).
   - Subtotal, pajak, diskon, dan total per orang otomatis dihitung secara proporsional.
   - Klik **Simpan Peserta**.
   - Ulangi hingga semua menu pada struk habis teralokasikan.
   - Klik **Selesai & Review Hasil**.

5. **Langkah 4 — Review & Simpan Hasil:**
   - Periksa ringkasan pembagian tiap peserta dalam kartu grid responsif.
   - Total tiap peserta tampil tebal dan mencolok.
   - Klik **Simpan Hasil Splitbill**.

6. **Langkah 5 & Detail Tagihan (`/tagihan/<token>`):**
   - Dapatkan URL unik yang aman dan read-only.
   - Gunakan tombol **Salin URL** atau **Salin Rincian untuk WhatsApp** untuk membagikannya ke grup teman-teman.
   - Tagihan memiliki masa berlaku 10 menit dengan live countdown timer.

