# Panduan Kontribusi (Contributing Guide) 🤝

Terima kasih atas ketertarikan Anda untuk berkontribusi pada proyek **Smart Splitbill**! Kami sangat menyambut kontribusi dari komunitas, baik berupa perbaikan bug, penambahan fitur, peningkatan dokumentasi, maupun penyempurnaan desain.

---

## 📋 Alur Kontribusi (Pull Request Workflow)

Untuk berkontribusi melalui kode:

1. **Fork Repositori Ini**
   Klik tombol **Fork** di pojok kanan atas repositori ini di GitHub.

2. **Clone Fork Anda ke Komputer Lokal**
   ```bash
   git clone https://github.com/<username-anda>/smart_splitbill.git
   cd smart_splitbill
   ```

3. **Buat Cabang Fitur (*Feature Branch*) Baru**
   Gunakan nama cabang yang deskriptif:
   ```bash
   git checkout -b fitur/nama-fitur-anda
   # atau untuk perbaikan bug:
   git checkout -b fix/nama-bug
   ```

4. **Siapkan Lingkungan Pengembangan Lokal**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   # Masukkan GEMINI_API_KEY Anda di .env
   python manage.py migrate
   ```

5. **Lakukan Perubahan Kode**
   - Ikuti standar kode Python (PEP 8).
   - Pastikan kode modular dan mematuhi arsitektur service layer di dalam `splitbill/services/`.
   - Jangan menyertakan kunci rahasia (*API keys*, password, tokens) ke dalam commit.

6. **Jalankan Pengujian Otomatis (*Unit Tests*)**
   Pastikan semua pengujian berhasil sebelum mengajukan PR:
   ```bash
   python manage.py test splitbill.tests
   ```
   *Jika menambahkan fitur baru, sangat dianjurkan menambahkan unit test yang relevan.*

7. **Commit & Push Perubahan Anda**
   ```bash
   git add .
   git commit -m "feat: tambahkan fitur kalkulasi tip opsional"
   git push origin fitur/nama-fitur-anda
   ```

8. **Buka Pull Request (PR)**
   - Buka repositori asli di GitHub dan klik **Compare & pull request**.
   - Jelaskan secara ringkas perubahan apa saja yang dibuat dan mengapa perubahan tersebut diperlukan.

---

## 🐛 Melaporkan Bug

Jika Anda menemukan bug:
1. Periksa tab **Issues** untuk memastikan isu serupa belum pernah dilaporkan sebelumnya.
2. Buat Issue baru dengan menyertakan:
   - Deskripsi ringkas mengenai masalah yang terjadi.
   - Langkah-langkah untuk mereproduksi bug (*Steps to Reproduce*).
   - Pesan error atau tangkapan layar jika ada.
   - Versi Python dan sistem operasi yang Anda gunakan.

---

## 💡 Mengajukan Ide / Fitur Baru

Punya ide untuk membuat Smart Splitbill lebih baik?
Silakan buka **Issue** baru dengan label `enhancement` dan jelaskan:
- Masalah apa yang ingin diselesaikan oleh fitur tersebut.
- Gambaran cara kerja fitur baru yang diusulkan.

---

Terima kasih telah membantu membuat Smart Splitbill menjadi lebih bermanfaat bagi semua orang! 🚀

