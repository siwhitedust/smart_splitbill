<div align="center">

# Panduan Kontribusi / Contributing Guide 🤝

---

**Pilih Bahasa / Select Language:**  
**[ 🇬🇧 English ](#-contributing-guide-english)** &nbsp;•&nbsp; **[ 🇮🇩 Bahasa Indonesia ](#-panduan-kontribusi-bahasa-indonesia)**

---

</div>

<br>

---

## 🇬🇧 Contributing Guide (English)

Thank you for your interest in contributing to **Smart Splitbill**! We welcome community contributions of all kinds: bug fixes, feature additions, documentation improvements, UI/UX polishing, and test additions.

---

### 📋 Pull Request Workflow

To contribute code:

1. **Fork the Repository**  
   Click the **Fork** button in the top-right corner of this repository on GitHub.

2. **Clone Your Fork Locally**  
   ```bash
   git clone https://github.com/<your-username>/smart_splitbill.git
   cd smart_splitbill
   ```

3. **Create a New Feature Branch**  
   Use descriptive branch names:
   ```bash
   git checkout -b feat/your-feature-name
   # or for bug fixes:
   git checkout -b fix/your-bug-name
   ```

4. **Setup Your Local Development Environment**  
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   # Add your GEMINI_API_KEY in .env
   python manage.py migrate
   ```

5. **Make Your Code Changes**  
   - Follow Python PEP 8 style standards.
   - Keep business logic inside modular service layers in `splitbill/services/`.
   - **Never commit secrets**, tokens, or private credentials into Git.

6. **Run Automated Tests**  
   Verify that all test cases pass before opening a Pull Request:
   ```bash
   python manage.py test splitbill.tests
   ```
   *If you add new features, please include corresponding unit test cases.*

7. **Commit & Push Your Work**  
   ```bash
   git add .
   git commit -m "feat: add optional tipping calculation"
   git push origin feat/your-feature-name
   ```

8. **Submit a Pull Request (PR)**  
   - Go to the original repository on GitHub and click **Compare & pull request**.
   - Provide a clear summary of what your changes do and why they are needed.

---

### 🐛 Reporting Bugs

If you find a bug:
1. Search the **Issues** tab to make sure it hasn't already been reported.
2. Open a new Issue and include:
   - A clear description of the bug.
   - Steps to reproduce the issue.
   - Error logs or screenshots (if applicable).
   - Your Python version and Operating System.

---

### 💡 Proposing New Features

Have an idea to make Smart Splitbill even better?  
Open an **Issue** with the `enhancement` label and describe:
- The problem your proposed feature solves.
- How you imagine the user workflow or implementation should look.

---

<br>

---

## 🇮🇩 Panduan Kontribusi (Bahasa Indonesia)

Terima kasih atas ketertarikan Anda untuk berkontribusi pada proyek **Smart Splitbill**! Kami sangat menyambut kontribusi dari komunitas, baik berupa perbaikan bug, penambahan fitur, peningkatan dokumentasi, maupun penyempurnaan desain.

---

### 📋 Alur Kontribusi (Pull Request Workflow)

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

### 🐛 Melaporkan Bug

Jika Anda menemukan bug:
1. Periksa tab **Issues** untuk memastikan isu serupa belum pernah dilaporkan sebelumnya.
2. Buat Issue baru dengan menyertakan:
   - Deskripsi ringkas mengenai masalah yang terjadi.
   - Langkah-langkah untuk mereproduksi bug (*Steps to Reproduce*).
   - Pesan error atau tangkapan layar jika ada.
   - Versi Python dan sistem operasi yang Anda gunakan.

---

### 💡 Mengajukan Ide / Fitur Baru

Punya ide untuk membuat Smart Splitbill lebih baik?  
Silakan buka **Issue** baru dengan label `enhancement` dan jelaskan:
- Masalah apa yang ingin diselesaikan oleh fitur tersebut.
- Gambaran cara kerja fitur baru yang diusulkan.

---

Thank you for contributing to Smart Splitbill! 🚀  
*Terima kasih telah membantu membuat Smart Splitbill menjadi lebih bermanfaat bagi semua orang!*
