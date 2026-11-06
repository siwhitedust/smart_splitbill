/**
 * Interaktivitas Wizard Smart Splitbill
 * State murni in-memory (RAM browser), tidak menyimpan ke localStorage / sessionStorage.
 * Menangani Upload/Kamera Foto, OCR, Validasi Hasil, Drag & Drop Pembagian Pesanan, dan Review.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Inisialisasi Mode dari query parameter ?mode=
    const urlParams = new URLSearchParams(window.location.search);
    const initialMode = urlParams.get('mode') === 'sendiri' ? 'sendiri' : 'bagi-rata';

    // State in-memory
    const state = {
        mode: initialMode, // 'bagi-rata' atau 'sendiri'
        currentStep: 1,
        selectedFile: null,
        billInfo: {
            restaurant_name: '',
            transaction_date: '',
            subtotal: 0,
            tax: 0,
            service: 0,
            discount: 0,
            other_fees: 0,
            grand_total: 0,
        },
        items: [],          // Array: [{id, name, qty, price, subtotal, confidence}]
        participants: [],   // Array untuk mode 'sendiri'
        editingParticipantIndex: -1, // -1 untuk peserta baru
        modalParticipantItems: [],   // Draft item di dalam modal
        equalSplit: {
            count: 2,
            participants: [
                { id: '1', name: 'Orang 1' },
                { id: '2', name: 'Orang 2' }
            ]
        }
    };

    // DOM Elements
    const steps = {
        1: document.getElementById('step-upload'),
        2: document.getElementById('step-ocr-review'),
        3: document.getElementById('step-split'),
        4: document.getElementById('step-final-review'),
        5: document.getElementById('step-confirmation'),
    };
    const stepEqualSplit = document.getElementById('step-equal-split');
    const stepperLabelStep3 = document.getElementById('stepper-label-step3');
    const btnProceedSplitText = document.getElementById('btn-proceed-split-text');

    // Equal Split DOM Elements
    const equalRestoName = document.getElementById('equal-resto-name');
    const equalGrandTotal = document.getElementById('equal-grand-total');
    const btnEqualMinus = document.getElementById('btn-equal-minus');
    const btnEqualPlus = document.getElementById('btn-equal-plus');
    const inputEqualCount = document.getElementById('input-equal-count');
    const equalPerPersonDisplay = document.getElementById('equal-per-person-display');
    const equalRemainderNote = document.getElementById('equal-remainder-note');
    const equalParticipantsList = document.getElementById('equal-participants-list');
    const btnEqualBackToOcr = document.getElementById('btn-equal-back-to-ocr');
    const btnEqualToReview = document.getElementById('btn-equal-to-review');

    // ==========================================
    // NAVBAR QUOTA BADGE HELPER
    // ==========================================
    function updateNavbarQuotaBadge(remainingQuota) {
        const badgeContainer = document.querySelector('.quota-badge');
        const quotaBadgeEl = document.querySelector('.quota-badge strong');
        const quotaIndicator = document.querySelector('.quota-indicator');

        if (!quotaBadgeEl) return;

        // Samarkan tampilan kuota agar selalu berformat 5/5
        if (remainingQuota === 'Unlimited') {
            remainingQuota = 5;
        }

        if (remainingQuota === 0 || remainingQuota === '0' || remainingQuota === 'Habis' || !remainingQuota) {
            quotaBadgeEl.textContent = '0';
            if (quotaIndicator) quotaIndicator.className = 'quota-indicator empty';
        } else {
            quotaBadgeEl.textContent = `${remainingQuota}/5`;
            if (quotaIndicator) {
                if (Number(remainingQuota) <= 2) {
                    quotaIndicator.className = 'quota-indicator low';
                } else {
                    quotaIndicator.className = 'quota-indicator';
                }
            }
        }
    }

    // ==========================================
    // STEP NAVIGATION & MODE CONTROL
    // ==========================================
    function setMode(mode) {
        state.mode = mode;
        const isBagiRata = mode === 'bagi-rata';

        if (stepperLabelStep3) {
            stepperLabelStep3.textContent = isBagiRata ? 'Jumlah Orang' : 'Bagi Pesanan';
        }

        if (btnProceedSplitText) {
            btnProceedSplitText.textContent = isBagiRata ? 'Lanjutkan ke Jumlah Orang' : 'Lanjutkan ke Pembagian Pesanan';
        }

        // Sinkronkan URL jika browser mendukung
        if (window.history && window.history.replaceState) {
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.set('mode', mode);
            window.history.replaceState({}, '', newUrl.toString());
        }

        // Jika sedang di step 3, refresh step yang aktif
        if (state.currentStep === 3) {
            goToStep(3);
        }
    }

    // Terapkan mode awal
    setMode(state.mode);

    function goToStep(stepNumber) {
        state.currentStep = stepNumber;

        Object.keys(steps).forEach(k => {
            const stepKey = parseInt(k, 10);
            if (steps[stepKey]) {
                if (stepKey === 3) {
                    if (state.mode === 'bagi-rata') {
                        steps[3].classList.remove('active');
                        if (stepEqualSplit) stepEqualSplit.classList.toggle('active', stepNumber === 3);
                    } else {
                        if (stepEqualSplit) stepEqualSplit.classList.remove('active');
                        steps[3].classList.toggle('active', stepNumber === 3);
                    }
                } else {
                    steps[stepKey].classList.toggle('active', stepKey === stepNumber);
                }
            }
        });

        if (stepNumber !== 3 && stepEqualSplit) {
            stepEqualSplit.classList.remove('active');
        }

        // Update stepper nav jika ada
        document.querySelectorAll('.stepper-item').forEach(item => {
            const itemStep = parseInt(item.getAttribute('data-step') || '0', 10);
            item.classList.toggle('active', itemStep === stepNumber);
            item.classList.toggle('completed', itemStep < stepNumber);
        });

        if (stepNumber === 3) {
            if (state.mode === 'bagi-rata') {
                renderEqualSplit();
            } else {
                initStepSplit();
            }
        } else if (stepNumber === 4) {
            initStepReview();
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // ==========================================
    // STEP 1: UPLOAD / KAMERA & OCR
    // ==========================================
    const receiptInput = document.getElementById('receipt-file-input');
    const cameraInput = document.getElementById('receipt-camera-input');
    const uploadDropzone = document.getElementById('upload-dropzone');
    const uploadPlaceholder = document.getElementById('upload-placeholder');
    const uploadPreview = document.getElementById('upload-preview');
    const previewImg = document.getElementById('preview-image');
    const btnProcessOcr = document.getElementById('btn-process-ocr');
    const btnChangePhoto = document.getElementById('btn-change-photo');
    const ocrLoading = document.getElementById('ocr-loading');
    const ocrBtnText = document.getElementById('ocr-btn-text');

    function handleFileSelection(file) {
        if (!file) return;

        // Validasi ekstensi
        const validExtensions = ['.jpg', '.jpeg', '.png', '.webp'];
        const fileName = file.name.toLowerCase();
        const isValidExt = validExtensions.some(ext => fileName.endsWith(ext));

        if (!isValidExt) {
            showToast("Hanya file gambar JPG, PNG, atau WEBP yang didukung.", 'danger');
            return;
        }

        // Validasi ukuran (5MB)
        if (file.size > 5 * 1024 * 1024) {
            showToast("Ukuran foto maksimal 5 MB.", 'danger');
            return;
        }

        state.selectedFile = file;

        // Tampilkan preview
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
            uploadPlaceholder.style.display = 'none';
            uploadPreview.style.display = 'block';
            btnProcessOcr.disabled = false;
        };
        reader.readAsDataURL(file);
    }

    if (receiptInput) {
        receiptInput.addEventListener('click', (e) => { e.target.value = ''; });
        receiptInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleFileSelection(e.target.files[0]);
            }
        });
    }
    if (cameraInput) {
        cameraInput.addEventListener('click', (e) => { e.target.value = ''; });
        cameraInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleFileSelection(e.target.files[0]);
            }
        });
    }

    if (uploadDropzone) {
        uploadDropzone.addEventListener('click', (e) => {
            if (e.target.closest('#receipt-camera-input') || e.target.closest('label[for="receipt-camera-input"]')) {
                return;
            }
            if (e.target.closest('#receipt-file-input') || e.target.closest('label[for="receipt-file-input"]')) {
                return;
            }
            if (e.target.closest('#btn-change-photo')) {
                return;
            }
            if (receiptInput && !state.selectedFile) {
                receiptInput.click();
            }
        });

        uploadDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadDropzone.classList.add('drag-active');
        });
        uploadDropzone.addEventListener('dragleave', () => {
            uploadDropzone.classList.remove('drag-active');
        });
        uploadDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadDropzone.classList.remove('drag-active');
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleFileSelection(e.dataTransfer.files[0]);
            }
        });
    }

    if (btnChangePhoto) {
        btnChangePhoto.addEventListener('click', () => {
            state.selectedFile = null;
            previewImg.src = '';
            uploadPreview.style.display = 'none';
            uploadPlaceholder.style.display = 'block';
            btnProcessOcr.disabled = true;
            if (receiptInput) receiptInput.value = '';
            if (cameraInput) cameraInput.value = '';
        });
    }

    // Kirim Foto ke API OCR
    if (btnProcessOcr) {
        const originalOcrBtnHtml = btnProcessOcr.innerHTML;

        btnProcessOcr.addEventListener('click', async () => {
            if (!state.selectedFile) {
                showToast("Pilih foto struk terlebih dahulu.", 'warning');
                return;
            }

            btnProcessOcr.disabled = true;
            // Hapus teks 'Baca Struk Pembayaran' dan sisakan HANYA animasi spinner + Loading...
            btnProcessOcr.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; gap: 0.5rem;">
                    <div class="spinner"></div>
                    <span>Loading...</span>
                </div>
            `;

            const formData = new FormData();
            formData.append('receipt_image', state.selectedFile);

            try {
                const response = await fetch('/api/ocr/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: formData,
                });

                const result = await response.json();

                if (!response.ok || result.status !== 'success') {
                    if (response.status === 503 || (result.message && (result.message.includes('server sedang sibuk') || result.message.includes('503') || result.message.includes('Semua model') || result.message.includes('timeout') || result.message.includes('timed out')))) {
                        throw new Error('server sedang sibuk');
                    }
                    if (response.status === 429 || (result.message && result.message.includes('kuota 1 hari sudah habis'))) {
                        // Update badge di navbar jika ada
                        updateNavbarQuotaBadge('Habis');
                        throw new Error('kuota 1 hari sudah habis see you besok');
                    }
                    throw new Error(result.message || 'Gagal memproses struk.');
                }

                // Perbarui sisa kuota jika ada di navbar
                if (result.remaining_quota !== undefined) {
                    updateNavbarQuotaBadge(result.remaining_quota);
                }

                // Sukses membaca OCR
                showToast("Struk berhasil dibaca! Silakan periksa hasilnya.", 'success');
                populateOcrReview(result.data);
                goToStep(2);
            } catch (err) {
                let msg = err.message || "Gagal memproses foto struk.";
                if (msg.includes("server sedang sibuk") || msg.includes("503") || msg.includes("Semua model") || msg.includes("UNAVAILABLE") || msg.includes("High demand") || msg.includes("timeout") || msg.includes("timed out")) {
                    msg = "server sedang sibuk";
                }
                showToast(msg, 'danger');
            } finally {
                btnProcessOcr.disabled = false;
                btnProcessOcr.innerHTML = originalOcrBtnHtml;
            }
        });
    }

    // ==========================================
    // STEP 2: FORM VALIDASI HASIL OCR
    // ==========================================
    const restoNameInput = document.getElementById('input-restaurant-name');
    const transDateInput = document.getElementById('input-transaction-date');
    const itemsTableBody = document.getElementById('items-table-body');
    const btnAddItem = document.getElementById('btn-add-item');
    const inputTax = document.getElementById('input-tax');
    const inputService = document.getElementById('input-service');
    const inputDiscount = document.getElementById('input-discount');
    const inputOtherFees = document.getElementById('input-other-fees');
    const inputGrandTotal = document.getElementById('input-grand-total');
    const textSubtotalCalc = document.getElementById('text-subtotal-calc');
    const textCalcGrandTotal = document.getElementById('text-calc-grand-total');
    const discrepancyWarning = document.getElementById('discrepancy-warning');
    const discrepancyAmountEl = document.getElementById('discrepancy-amount');
    const btnFixTotal = document.getElementById('btn-fix-total');
    const btnProceedToSplit = document.getElementById('btn-proceed-to-split');

    function populateOcrReview(data) {
        state.billInfo.restaurant_name = data.restaurant_name || '';
        state.billInfo.transaction_date = data.transaction_date || '';
        state.billInfo.service = parseNumber(data.service);
        state.billInfo.discount = parseNumber(data.discount);
        state.billInfo.other_fees = parseNumber(data.other_fees);
        state.billInfo.grand_total = parseNumber(data.grand_total);

        // Items
        state.items = (data.items || []).map((it, idx) => ({
            id: it.id || (idx + 1),
            name: it.name || '',
            qty: parseNumber(it.qty) || 1,
            price: parseNumber(it.price || it.unit_price) || 0,
            subtotal: (parseNumber(it.qty) || 1) * (parseNumber(it.price || it.unit_price) || 0),
            confidence: it.confidence || 'high',
        }));

        if (state.items.length === 0) {
            state.items.push({ id: 1, name: '', qty: 1, price: 0, subtotal: 0, confidence: 'high' });
        }

        // Jika pada struk tertulis pajak sudah termasuk (Tax Inclusive / Harga termasuk PPN)
        // atau jika jumlah harga seluruh item sudah sama dengan grand_total, maka isi nilai tax dengan 0
        const calculatedItemsSum = state.items.reduce((acc, it) => acc + it.subtotal, 0);
        const grandTotalVal = state.billInfo.grand_total;
        const isTaxInclusive = Boolean(data.is_tax_inclusive);

        if (isTaxInclusive || (calculatedItemsSum > 0 && Math.abs(calculatedItemsSum - grandTotalVal) < 1)) {
            state.billInfo.tax = 0;
        } else {
            state.billInfo.tax = parseNumber(data.tax);
        }

        restoNameInput.value = state.billInfo.restaurant_name;
        transDateInput.value = state.billInfo.transaction_date;
        inputTax.value = state.billInfo.tax !== 0 ? state.billInfo.tax : 0;
        inputService.value = state.billInfo.service || '';
        inputDiscount.value = state.billInfo.discount || '';
        inputOtherFees.value = state.billInfo.other_fees || '';
        inputGrandTotal.value = state.billInfo.grand_total || '';

        renderItemsTable();
        recalculateOcrTotals();
    }

    function renderItemsTable() {
        itemsTableBody.innerHTML = '';
        state.items.forEach((item, index) => {
            const tr = document.createElement('tr');
            tr.className = item.confidence === 'low' ? 'row-low-confidence' : '';
            tr.innerHTML = `
                <td style="padding: 0.35rem 0.4rem;">
                    <div style="display:flex;align-items:center;gap:0.4rem;">
                        <input type="text" class="form-control item-name-input" data-index="${index}" value="${escapeHtml(item.name)}" placeholder="Nama menu..." style="min-width: 210px;" required>
                        ${item.confidence === 'low' ? '<span title="Hasil bacaan item ini perlu diperiksa" style="color:#b45309;font-size:0.75rem;cursor:help;">⚠️</span>' : ''}
                    </div>
                </td>
                <td style="width: 75px; padding: 0.35rem 0.4rem;">
                    <input type="number" step="any" min="0.1" class="form-control item-qty-input" data-index="${index}" value="${item.qty}" style="text-align:center;" required>
                </td>
                <td style="width: 135px; padding: 0.35rem 0.4rem;">
                    <input type="number" step="any" min="0" class="form-control item-price-input" data-index="${index}" value="${item.price}" placeholder="Harga satuan" required>
                </td>
                <td style="width: 125px; padding: 0.35rem 0.4rem; font-weight:600; text-align:right; color:var(--text-main);">
                    <span class="item-subtotal-text">${formatRupiah(item.subtotal)}</span>
                </td>
                <td style="width: 44px; padding: 0.35rem 0.4rem; text-align:center;">
                    <button type="button" class="btn btn-ghost btn-icon-only btn-remove-item" data-index="${index}" title="Hapus baris" style="width:30px;height:30px;">
                        <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                    </button>
                </td>
            `;
            itemsTableBody.appendChild(tr);
        });

        // Event listeners untuk input tabel
        itemsTableBody.querySelectorAll('.item-name-input').forEach(input => {
            input.addEventListener('input', (e) => {
                const idx = parseInt(e.target.dataset.index);
                state.items[idx].name = e.target.value;
            });
        });

        itemsTableBody.querySelectorAll('.item-qty-input').forEach(input => {
            input.addEventListener('input', (e) => {
                const idx = parseInt(e.target.dataset.index);
                const q = parseNumber(e.target.value) || 0;
                state.items[idx].qty = q;
                state.items[idx].subtotal = q * state.items[idx].price;
                renderItemSubtotalText(idx);
                recalculateOcrTotals();
            });
        });

        itemsTableBody.querySelectorAll('.item-price-input').forEach(input => {
            input.addEventListener('input', (e) => {
                const idx = parseInt(e.target.dataset.index);
                const p = parseNumber(e.target.value) || 0;
                state.items[idx].price = p;
                state.items[idx].subtotal = state.items[idx].qty * p;
                renderItemSubtotalText(idx);
                recalculateOcrTotals();
            });
        });

        itemsTableBody.querySelectorAll('.btn-remove-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.currentTarget.dataset.index);
                if (state.items.length <= 1) {
                    showToast("Struk harus memiliki minimal 1 item pesanan.", 'warning');
                    return;
                }
                state.items.splice(idx, 1);
                renderItemsTable();
                recalculateOcrTotals();
            });
        });
    }

    function renderItemSubtotalText(idx) {
        const rows = itemsTableBody.querySelectorAll('tr');
        if (rows[idx]) {
            const subText = rows[idx].querySelector('.item-subtotal-text');
            if (subText) subText.textContent = formatRupiah(state.items[idx].subtotal);
        }
    }

    function recalculateOcrTotals() {
        const subtotal = state.items.reduce((acc, it) => acc + (it.qty * it.price), 0);
        state.billInfo.subtotal = subtotal;

        const tax = parseNumber(inputTax.value);
        const service = parseNumber(inputService.value);
        const discount = parseNumber(inputDiscount.value);
        const otherFees = parseNumber(inputOtherFees.value);
        const grandTotal = parseNumber(inputGrandTotal.value);

        state.billInfo.tax = tax;
        state.billInfo.service = service;
        state.billInfo.discount = discount;
        state.billInfo.other_fees = otherFees;
        state.billInfo.grand_total = grandTotal;

        const expectedTotal = subtotal + tax + service + otherFees - discount;

        textSubtotalCalc.textContent = formatRupiah(subtotal);
        textCalcGrandTotal.textContent = formatRupiah(expectedTotal);

        // Deteksi discrepancy selisih total
        const diff = Math.abs(expectedTotal - grandTotal);
        if (diff >= 1) {
            discrepancyWarning.style.display = 'flex';
            discrepancyAmountEl.textContent = `${formatRupiah(expectedTotal)} vs tertulis ${formatRupiah(grandTotal)} (selisih: ${formatRupiah(expectedTotal - grandTotal)})`;
        } else {
            discrepancyWarning.style.display = 'none';
        }
    }

    if (btnAddItem) {
        btnAddItem.addEventListener('click', () => {
            const newId = (state.items.length > 0 ? Math.max(...state.items.map(i => i.id || 0)) : 0) + 1;
            state.items.push({
                id: newId,
                name: '',
                qty: 1,
                price: 0,
                subtotal: 0,
                confidence: 'high',
            });
            renderItemsTable();
            recalculateOcrTotals();
        });
    }

    [inputTax, inputService, inputDiscount, inputOtherFees, inputGrandTotal].forEach(el => {
        if (el) el.addEventListener('input', recalculateOcrTotals);
    });

    if (btnFixTotal) {
        btnFixTotal.addEventListener('click', () => {
            const expected = state.billInfo.subtotal + state.billInfo.tax + state.billInfo.service + state.billInfo.other_fees - state.billInfo.discount;
            inputGrandTotal.value = Math.round(expected);
            recalculateOcrTotals();
            showToast("Grand total telah disesuaikan dengan perhitungan item.", 'success');
        });
    }

    if (btnProceedToSplit) {
        btnProceedToSplit.addEventListener('click', () => {
            // Validasi nama restoran
            state.billInfo.restaurant_name = restoNameInput.value.trim() || 'Restoran / Kafe';
            state.billInfo.transaction_date = transDateInput.value.trim();

            if (state.mode === 'bagi-rata') {
                if (state.billInfo.grand_total <= 0) {
                    showToast("Total tagihan harus lebih dari Rp0.", 'warning');
                    return;
                }
                goToStep(3);
                return;
            }

            // Validasi items
            for (let i = 0; i < state.items.length; i++) {
                const it = state.items[i];
                if (!it.name.trim()) {
                    showToast(`Nama item #${i + 1} tidak boleh kosong.`, 'warning');
                    return;
                }
                if (it.qty <= 0) {
                    showToast(`Kuantitas untuk "${it.name}" harus lebih dari 0.`, 'warning');
                    return;
                }
                if (it.price < 0) {
                    showToast(`Harga untuk "${it.name}" tidak boleh negatif.`, 'warning');
                    return;
                }
            }

            // Pindah ke step pembagian
            goToStep(3);
        });
    }

    // ==========================================
    // TOMBOL BATALKAN DI STEP 2 (PERIKSA HASIL)
    // ==========================================
    const btnCancelOcrReview = document.getElementById('btn-cancel-ocr-review');
    const cancelOcrModal = document.getElementById('cancel-ocr-modal');
    const btnCloseCancelModalX = document.getElementById('btn-close-cancel-modal-x');
    const btnDismissCancelModal = document.getElementById('btn-dismiss-cancel-modal');
    const btnConfirmCancelOcr = document.getElementById('btn-confirm-cancel-ocr');

    if (btnCancelOcrReview && cancelOcrModal) {
        btnCancelOcrReview.addEventListener('click', () => {
            cancelOcrModal.classList.add('active');
        });

        const closeCancelModal = () => {
            cancelOcrModal.classList.remove('active');
        };

        if (btnCloseCancelModalX) btnCloseCancelModalX.addEventListener('click', closeCancelModal);
        if (btnDismissCancelModal) btnDismissCancelModal.addEventListener('click', closeCancelModal);
        cancelOcrModal.addEventListener('click', (e) => {
            if (e.target === cancelOcrModal) closeCancelModal();
        });

        if (btnConfirmCancelOcr) {
            btnConfirmCancelOcr.addEventListener('click', () => {
                closeCancelModal();

                // 1. Reset State
                state.selectedFile = null;
                state.billInfo = {
                    restaurant_name: '',
                    transaction_date: '',
                    subtotal: 0,
                    tax: 0,
                    service: 0,
                    discount: 0,
                    other_fees: 0,
                    grand_total: 0,
                };
                state.items = [];
                state.participants = [];
                state.editingParticipantIndex = -1;
                state.modalParticipantItems = [];
                state.equalSplit = {
                    count: 2,
                    participants: [
                        { id: '1', name: 'Orang 1' },
                        { id: '2', name: 'Orang 2' }
                    ]
                };
                if (inputEqualCount) inputEqualCount.value = 2;

                // 2. Reset Step 1 Elements
                if (previewImg) previewImg.src = '';
                if (uploadPreview) uploadPreview.style.display = 'none';
                if (uploadPlaceholder) uploadPlaceholder.style.display = 'block';
                if (btnProcessOcr) btnProcessOcr.disabled = true;
                if (receiptInput) receiptInput.value = '';
                if (cameraInput) cameraInput.value = '';

                // 3. Reset Step 2 Input Elements
                if (restoNameInput) restoNameInput.value = '';
                if (transDateInput) transDateInput.value = '';
                if (inputTax) inputTax.value = '';
                if (inputService) inputService.value = '';
                if (inputDiscount) inputDiscount.value = '';
                if (inputOtherFees) inputOtherFees.value = '';
                if (inputGrandTotal) inputGrandTotal.value = '';
                if (itemsTableBody) itemsTableBody.innerHTML = '';
                if (textSubtotalCalc) textSubtotalCalc.textContent = 'Rp0';
                if (textCalcGrandTotal) textCalcGrandTotal.textContent = 'Rp0';
                if (discrepancyWarning) discrepancyWarning.style.display = 'none';

                // 4. Kembali ke Step 1
                goToStep(1);

                showToast("Pemeriksaan struk dibatalkan. Kuota Anda tidak berkurang.", 'info');
            });
        }
    }

    // ==========================================
    // STEP 3 (BAGI RATA): EQUAL SPLIT LOGIC
    // ==========================================
    function calculateEqualSplitAmounts() {
        const grandTotal = Math.round(state.billInfo.grand_total || 0);
        let count = parseInt(inputEqualCount ? inputEqualCount.value : state.equalSplit.count, 10);
        if (isNaN(count) || count < 1) count = 2;
        state.equalSplit.count = count;

        const baseAmount = Math.floor(grandTotal / count);
        const remainder = grandTotal % count;

        // Pastikan array participants sinkron dengan count
        while (state.equalSplit.participants.length < count) {
            const newIndex = state.equalSplit.participants.length + 1;
            state.equalSplit.participants.push({
                id: String(newIndex),
                name: `Orang ${newIndex}`
            });
        }
        if (state.equalSplit.participants.length > count) {
            state.equalSplit.participants = state.equalSplit.participants.slice(0, count);
        }

        return { grandTotal, count, baseAmount, remainder };
    }

    function renderEqualSplit() {
        if (!stepEqualSplit) return;

        if (equalRestoName) {
            equalRestoName.textContent = state.billInfo.restaurant_name || 'Restoran / Kafe';
        }

        const { grandTotal, count, baseAmount, remainder } = calculateEqualSplitAmounts();

        if (equalGrandTotal) {
            equalGrandTotal.textContent = formatRupiah(grandTotal);
        }

        if (equalPerPersonDisplay) {
            if (remainder === 0) {
                equalPerPersonDisplay.textContent = formatRupiah(baseAmount);
            } else {
                equalPerPersonDisplay.textContent = `${formatRupiah(baseAmount)} - ${formatRupiah(baseAmount + 1)}`;
            }
        }

        if (equalRemainderNote) {
            if (remainder === 0) {
                equalRemainderNote.innerHTML = `Presisi Rupiah Pas: Semua <strong>${count} orang</strong> membayar tepat <strong>${formatRupiah(baseAmount)}</strong>.`;
            } else {
                equalRemainderNote.innerHTML = `Presisi Rupiah Pas: <strong>${remainder} orang</strong> membayar <strong>${formatRupiah(baseAmount + 1)}</strong> dan <strong>${count - remainder} orang</strong> membayar <strong>${formatRupiah(baseAmount)}</strong> (Total tepat <strong>${formatRupiah(grandTotal)}</strong> tanpa selisih).`;
            }
        }

        // Render quick chips active status
        document.querySelectorAll('.quick-chip').forEach(chip => {
            const chipCount = parseInt(chip.getAttribute('data-count'), 10);
            chip.classList.toggle('active', chipCount === count);
        });

        // Render participants list
        if (equalParticipantsList) {
            equalParticipantsList.innerHTML = '';
            state.equalSplit.participants.forEach((p, idx) => {
                const pAmount = idx < remainder ? (baseAmount + 1) : baseAmount;
                const row = document.createElement('div');
                row.className = 'equal-participant-row';
                row.innerHTML = `
                    <div style="display:flex;align-items:center;gap:0.5rem;flex:1;min-width:0;">
                        <span style="font-size:1.15rem;">👤</span>
                        <input type="text" class="form-control form-control-sm equal-p-name-input" data-index="${idx}" value="${escapeHtml(p.name)}" placeholder="Nama Peserta ${idx + 1}" style="font-weight:600;font-size:0.875rem;max-width:160px;">
                    </div>
                    <div style="text-align:right;white-space:nowrap;">
                        <span style="font-weight:800;font-size:1rem;color:var(--text-main);">${formatRupiah(pAmount)}</span>
                    </div>
                `;
                equalParticipantsList.appendChild(row);
            });

            equalParticipantsList.querySelectorAll('.equal-p-name-input').forEach(input => {
                input.addEventListener('input', (e) => {
                    const idx = parseInt(e.target.dataset.index, 10);
                    const val = e.target.value.trim();
                    if (state.equalSplit.participants[idx]) {
                        state.equalSplit.participants[idx].name = val || `Orang ${idx + 1}`;
                    }
                });
            });
        }
    }

    if (btnEqualMinus) {
        btnEqualMinus.addEventListener('click', () => {
            let current = parseInt(inputEqualCount ? inputEqualCount.value : '2', 10) || 2;
            if (current > 1) {
                if (inputEqualCount) inputEqualCount.value = current - 1;
                renderEqualSplit();
            }
        });
    }

    if (btnEqualPlus) {
        btnEqualPlus.addEventListener('click', () => {
            let current = parseInt(inputEqualCount ? inputEqualCount.value : '2', 10) || 2;
            if (current < 100) {
                if (inputEqualCount) inputEqualCount.value = current + 1;
                renderEqualSplit();
            }
        });
    }

    if (inputEqualCount) {
        inputEqualCount.addEventListener('input', () => {
            let val = parseInt(inputEqualCount.value, 10);
            if (isNaN(val) || val < 1) val = 1;
            if (val > 100) val = 100;
            renderEqualSplit();
        });
    }

    document.querySelectorAll('.quick-chip').forEach(chip => {
        chip.addEventListener('click', (e) => {
            const count = parseInt(e.currentTarget.getAttribute('data-count'), 10);
            if (count && inputEqualCount) {
                inputEqualCount.value = count;
                renderEqualSplit();
            }
        });
    });

    if (btnEqualBackToOcr) {
        btnEqualBackToOcr.addEventListener('click', () => {
            goToStep(2);
        });
    }

    if (btnEqualToReview) {
        btnEqualToReview.addEventListener('click', () => {
            calculateEqualSplitAmounts();
            initStepReview();
            goToStep(4);
        });
    }

    // ==========================================
    // STEP 3: PEMBAGIAN PESANAN PER ORANG
    // ==========================================
    const participantsListEl = document.getElementById('participants-list');
    const allocationSummaryEl = document.getElementById('allocation-status-summary');
    const btnAddParticipant = document.getElementById('btn-add-participant');
    const btnBackToOcr = document.getElementById('btn-back-to-ocr');
    const btnFinishToReview = document.getElementById('btn-finish-to-review');

    // Modal Elements
    const participantModal = document.getElementById('participant-modal');
    const modalTitle = document.getElementById('modal-participant-title');
    const modalParticipantName = document.getElementById('modal-participant-name');
    const modalReceiptItemsList = document.getElementById('modal-receipt-items-list');
    const modalSelectedItemsList = document.getElementById('modal-selected-items-list');
    const modalSubtotalText = document.getElementById('modal-subtotal-text');
    const modalTaxText = document.getElementById('modal-tax-text');
    const modalServiceText = document.getElementById('modal-service-text');
    const modalDiscountText = document.getElementById('modal-discount-text');
    const modalTotalText = document.getElementById('modal-total-text');
    const btnCancelModal = document.getElementById('btn-cancel-modal');
    const btnCloseModalX = document.getElementById('btn-close-modal-x');
    const btnSaveParticipant = document.getElementById('btn-save-participant');

    function initStepSplit() {
        renderParticipantsList();
        renderAllocationStatus();
    }

    function calculateAllocatedQuantities(excludeParticipantIndex = -1) {
        const allocated = {};
        state.items.forEach(it => { allocated[it.id] = 0; });

        state.participants.forEach((p, pIdx) => {
            if (pIdx === excludeParticipantIndex) return;
            p.items.forEach(pItem => {
                const itId = pItem.item_id;
                if (allocated[itId] !== undefined) {
                    allocated[itId] += pItem.qty;
                }
            });
        });
        return allocated;
    }

    function renderAllocationStatus() {
        const allocated = calculateAllocatedQuantities();
        const hasItems = state.items && state.items.length > 0;
        const hasParticipants = state.participants && state.participants.length > 0;
        
        let allCompleted = hasItems && hasParticipants;
        let hasOverAllocated = false;
        let html = '';

        state.items.forEach(it => {
            const alloc = allocated[it.id] || 0;
            const remaining = it.qty - alloc;
            const isDone = Math.abs(remaining) < 0.001;
            const isOver = remaining < -0.001;

            if (!isDone) allCompleted = false;
            if (isOver) hasOverAllocated = true;

            let badgeClass = isDone ? 'qty-badge' : (isOver ? 'qty-badge depleted' : 'qty-badge');
            let statusText = isDone
                ? 'Teralokasi tuntas'
                : (isOver ? `Kelebihan ${Math.abs(remaining)}` : `Sisa ${remaining}`);

            html += `
                <div style="display:inline-flex;align-items:center;gap:0.4rem;font-size:0.8rem;background:var(--card-bg-subtle);padding:0.25rem 0.6rem;border-radius:20px;border:1px solid var(--glass-border);color:var(--text-main);margin:0.2rem;">
                    <span>${escapeHtml(it.name)} (${it.qty}):</span>
                    <strong style="color:${isDone ? '#15803d' : (isOver ? '#b91c1c' : '#b45309')};">${statusText}</strong>
                </div>
            `;
        });

        if (allocationSummaryEl) {
            allocationSummaryEl.innerHTML = html;
        }

        // Update badge ringkasan & helper text di Step 3
        const globalBadge = document.getElementById('allocation-global-badge');
        const helperText = document.getElementById('allocation-helper-text');

        if (globalBadge) {
            if (allCompleted) {
                globalBadge.style.background = 'var(--status-success-bg)';
                globalBadge.style.color = 'var(--status-success)';
                globalBadge.style.border = '1px solid var(--status-success-border)';
                globalBadge.textContent = '✓ Alokasi Selesai';
            } else if (!hasParticipants) {
                globalBadge.style.background = 'var(--status-warning-bg)';
                globalBadge.style.color = 'var(--status-warning)';
                globalBadge.style.border = '1px solid var(--status-warning-border)';
                globalBadge.textContent = 'Belum Ada Peserta';
            } else if (hasOverAllocated) {
                globalBadge.style.background = 'var(--status-danger-bg)';
                globalBadge.style.color = 'var(--status-danger)';
                globalBadge.style.border = '1px solid var(--status-danger-border)';
                globalBadge.textContent = 'Kelebihan Porsi';
            } else {
                globalBadge.style.background = 'var(--status-warning-bg)';
                globalBadge.style.color = 'var(--status-warning)';
                globalBadge.style.border = '1px solid var(--status-warning-border)';
                globalBadge.textContent = 'Alokasi Belum Selesai';
            }
        }

        if (helperText) {
            if (allCompleted) {
                helperText.style.color = 'var(--status-success)';
                helperText.textContent = '✓ Semua pesanan telah dibagikan dengan pas. Tombol "Selesai & Review Hasil" sudah aktif.';
            } else if (!hasParticipants) {
                helperText.style.color = 'var(--text-muted)';
                helperText.textContent = 'Klik tombol "+ Tambah Orang" di atas untuk mulai membagikan menu struk.';
            } else if (hasOverAllocated) {
                helperText.style.color = 'var(--status-danger)';
                helperText.textContent = '⚠️ Ada menu yang dibagikan melebihi jumlah porsi pada struk. Tombol selesai dinonaktifkan.';
            } else {
                helperText.style.color = 'var(--status-warning)';
                helperText.textContent = '⚠️ Bagikan seluruh sisa menu struk di atas agar tombol selesai dapat ditekan.';
            }
        }

        // Logic disable/enable tombol Selesai & Review Hasil
        if (btnFinishToReview) {
            btnFinishToReview.disabled = !allCompleted;
            if (allCompleted) {
                btnFinishToReview.classList.remove('btn-disabled');
                btnFinishToReview.style.cursor = 'pointer';
                btnFinishToReview.title = 'Semua menu sudah teralokasi, klik untuk lanjut ke review hasil';
            } else {
                btnFinishToReview.classList.add('btn-disabled');
                btnFinishToReview.style.cursor = 'not-allowed';
                if (!hasParticipants) {
                    btnFinishToReview.title = 'Tambahkan minimal satu orang peserta terlebih dahulu';
                } else if (hasOverAllocated) {
                    btnFinishToReview.title = 'Ada menu yang dialokasikan melebihi jumlah struk';
                } else {
                    btnFinishToReview.title = 'Alokasikan seluruh porsi menu ke peserta sampai tuntas untuk melanjutkan';
                }
            }
        }

        return allCompleted;
    }

    function renderParticipantsList() {
        participantsListEl.innerHTML = '';

        if (state.participants.length === 0) {
            participantsListEl.innerHTML = `
                <div class="empty-state" style="padding: 2rem 1rem;">
                    <div class="empty-state-title">Belum ada peserta</div>
                    <p style="font-size: 0.9rem;">Klik tombol "Tambah Orang" untuk mulai membagikan pesanan struk.</p>
                </div>
            `;
            return;
        }

        state.participants.forEach((p, index) => {
            const card = document.createElement('div');
            card.className = 'glass-card participant-card-item';

            // Hitung subtotal peserta
            const pSubtotal = p.items.reduce((acc, it) => acc + (it.qty * it.price), 0);

            // Ringkasan item
            const itemsSummary = p.items.length > 0
                ? p.items.map(it => `<span style="display:inline-block;background:var(--card-bg-subtle);padding:0.15rem 0.45rem;border-radius:4px;border:1px solid var(--glass-border);margin:0.15rem 0.2rem 0.15rem 0;font-size:0.785rem;">${it.qty}x ${escapeHtml(it.name)}</span>`).join('')
                : '<span style="color:var(--text-light);font-style:italic;font-size:0.8rem;">Belum memilih pesanan</span>';

            card.innerHTML = `
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:0.5rem;margin-bottom:0.5rem;">
                    <div style="display:flex;align-items:center;gap:0.4rem;min-width:0;">
                        <span style="font-size:1.05rem;">👤</span>
                        <h4 style="font-size:1.025rem;font-weight:700;color:var(--text-main);margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                            ${escapeHtml(p.name)}
                        </h4>
                    </div>
                    <div style="display:flex;gap:0.35rem;flex-shrink:0;">
                        <button type="button" class="btn btn-secondary btn-sm btn-edit-participant" data-index="${index}" style="padding:0.25rem 0.55rem;font-size:0.75rem;">
                            Edit
                        </button>
                        <button type="button" class="btn btn-ghost btn-sm btn-delete-participant" data-index="${index}" style="color:var(--status-danger);padding:0.25rem 0.45rem;font-size:0.75rem;" title="Hapus peserta">
                            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                        </button>
                    </div>
                </div>
                <div style="margin-bottom:0.65rem;min-height:2.2rem;line-height:1.3;flex:1;">
                    ${itemsSummary}
                </div>
                <div style="padding-top:0.5rem;border-top:1px dashed var(--glass-border);display:flex;justify-content:space-between;align-items:center;font-size:0.85rem;">
                    <span style="color:var(--text-muted);font-size:0.8rem;">Subtotal:</span>
                    <strong style="color:var(--text-main);font-weight:700;">${formatRupiah(pSubtotal)}</strong>
                </div>
            `;
            participantsListEl.appendChild(card);
        });

        participantsListEl.querySelectorAll('.btn-edit-participant').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.currentTarget.dataset.index);
                openParticipantModal(idx);
            });
        });

        participantsListEl.querySelectorAll('.btn-delete-participant').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const idx = parseInt(e.currentTarget.dataset.index);
                state.participants.splice(idx, 1);
                renderParticipantsList();
                renderAllocationStatus();
            });
        });
    }

    // Modal Pembagian Pesanan (Dua Drawer / Vertikal Mobile + Drag & Drop)
    function openParticipantModal(participantIndex = -1) {
        state.editingParticipantIndex = participantIndex;

        if (participantIndex >= 0) {
            // Edit peserta yang sudah ada
            const p = state.participants[participantIndex];
            modalTitle.textContent = `Edit Pesanan - ${p.name}`;
            modalParticipantName.value = p.name;
            // Deep copy items draft
            state.modalParticipantItems = p.items.map(it => ({ ...it }));
        } else {
            // Tambah peserta baru
            const pNum = state.participants.length + 1;
            modalTitle.textContent = `Tambah Peserta #${pNum}`;
            modalParticipantName.value = `Peserta ${pNum}`;
            state.modalParticipantItems = [];
        }

        renderModalDrawers();
        participantModal.classList.add('active');
    }

    function closeModal() {
        participantModal.classList.remove('active');
        state.editingParticipantIndex = -1;
        state.modalParticipantItems = [];
    }

    if (btnCancelModal) btnCancelModal.addEventListener('click', closeModal);
    if (btnCloseModalX) btnCloseModalX.addEventListener('click', closeModal);

    if (btnAddParticipant) {
        btnAddParticipant.addEventListener('click', () => openParticipantModal(-1));
    }

    function renderModalDrawers() {
        const allocated = calculateAllocatedQuantities(state.editingParticipantIndex);

        // 1. Kolom Kiri: Daftar Pesanan Struk
        modalReceiptItemsList.innerHTML = '';
        state.items.forEach(it => {
            const alreadyAlloc = allocated[it.id] || 0;
            // Hitung juga yang sedang dipilih di draft modal saat ini
            const inModalItem = state.modalParticipantItems.find(m => m.item_id === it.id);
            const inModalQty = inModalItem ? inModalItem.qty : 0;
            const remaining = Math.max(0, it.qty - alreadyAlloc - inModalQty);

            const div = document.createElement('div');
            div.className = `drag-item ${remaining <= 0 ? 'is-depleted' : ''}`;
            div.setAttribute('draggable', remaining > 0 ? 'true' : 'false');
            div.dataset.itemId = it.id;

            div.innerHTML = `
                <div class="drag-item-info">
                    <div class="drag-item-name" title="${escapeHtml(it.name)}">${escapeHtml(it.name)}</div>
                    <div class="drag-item-meta">
                        <span class="drag-item-price">${formatRupiah(it.price)}</span>
                        <span>&bull;</span>
                        <span>Total: ${it.qty}</span>
                    </div>
                </div>
                <div class="drag-item-actions">
                    <span class="qty-badge ${remaining > 0 ? 'available' : 'depleted'}">
                        ${remaining > 0 ? `Sisa ${remaining}` : 'Habis'}
                    </span>
                    <button type="button" class="btn btn-secondary btn-sm btn-click-add" data-id="${it.id}" ${remaining <= 0 ? 'disabled' : ''} title="${remaining > 0 ? 'Tambah ke peserta ini' : 'Porsi sudah habis teralokasi'}">
                        + Tambah
                    </button>
                </div>
            `;

            // HTML5 Drag Event
            if (remaining > 0) {
                div.addEventListener('dragstart', (e) => {
                    e.dataTransfer.setData('text/plain', JSON.stringify({ item_id: it.id }));
                    div.classList.add('dragging');
                });
                div.addEventListener('dragend', () => {
                    div.classList.remove('dragging');
                });
            }

            modalReceiptItemsList.appendChild(div);
        });

        // Alternatif Klik/Tap tombol "+ Tambah" (Mobile & Desktop Friendly!)
        modalReceiptItemsList.querySelectorAll('.btn-click-add').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const itemId = parseInt(e.currentTarget.dataset.id);
                addItemToParticipant(itemId);
            });
        });

        // 2. Kolom Kanan: Pesanan Orang Ini
        modalSelectedItemsList.innerHTML = '';
        if (state.modalParticipantItems.length === 0) {
            modalSelectedItemsList.innerHTML = `
                <div class="dropzone-target" id="modal-dropzone">
                    Tarik pesanan dari kiri ke sini<br>atau klik tombol "+ Tambah"
                </div>
            `;
        } else {
            state.modalParticipantItems.forEach((pIt, pIdx) => {
                const originalItem = state.items.find(i => i.id === pIt.item_id);
                const maxAvailable = originalItem ? (originalItem.qty - (allocated[pIt.item_id] || 0)) : pIt.qty;

                const div = document.createElement('div');
                div.className = 'glass-card';
                div.style.padding = '0.625rem 0.75rem';
                div.style.background = 'var(--card-bg)';
                div.innerHTML = `
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;">
                        <span style="font-weight:600;font-size:0.9rem;">${escapeHtml(pIt.name)}</span>
                        <button type="button" class="btn btn-ghost btn-icon-only btn-remove-modal-item" data-index="${pIdx}" style="width:28px;height:28px;padding:2px;color:var(--status-danger);">
                            ✕
                        </button>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center;font-size:0.85rem;">
                        <div style="display:flex;align-items:center;gap:0.4rem;">
                            <span>Porsi:</span>
                            <input type="number" step="any" min="0.1" max="${maxAvailable}" class="form-control modal-qty-input" data-index="${pIdx}" value="${pIt.qty}" style="width:65px;padding:0.25rem;text-align:center;">
                        </div>
                        <span style="font-weight:700;">${formatRupiah(pIt.qty * pIt.price)}</span>
                    </div>
                `;
                modalSelectedItemsList.appendChild(div);
            });

            modalSelectedItemsList.querySelectorAll('.modal-qty-input').forEach(input => {
                input.addEventListener('input', (e) => {
                    const idx = parseInt(e.target.dataset.index);
                    const val = parseNumber(e.target.value) || 0;
                    state.modalParticipantItems[idx].qty = val;
                    state.modalParticipantItems[idx].subtotal = val * state.modalParticipantItems[idx].price;
                    renderModalDrawers();
                });
            });

            modalSelectedItemsList.querySelectorAll('.btn-remove-modal-item').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const idx = parseInt(e.currentTarget.dataset.index);
                    state.modalParticipantItems.splice(idx, 1);
                    renderModalDrawers();
                });
            });
        }

        // Setup Dropzone Kolom Kanan
        const dropzone = document.getElementById('modal-dropzone') || modalSelectedItemsList;
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('drag-over');
        });
        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('drag-over');
        });
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('drag-over');
            try {
                const data = JSON.parse(e.dataTransfer.getData('text/plain'));
                if (data && data.item_id) {
                    addItemToParticipant(data.item_id);
                }
            } catch (err) { }
        });

        recalculateModalSummary();
    }

    function addItemToParticipant(itemId) {
        const targetItem = state.items.find(i => i.id === itemId);
        if (!targetItem) return;

        const allocated = calculateAllocatedQuantities(state.editingParticipantIndex);
        const existingInModal = state.modalParticipantItems.find(m => m.item_id === itemId);
        const alreadyAlloc = allocated[itemId] || 0;
        const currentInModalQty = existingInModal ? existingInModal.qty : 0;
        const remaining = targetItem.qty - alreadyAlloc - currentInModalQty;

        if (remaining <= 0) {
            return;
        }

        if (existingInModal) {
            existingInModal.qty += 1;
            existingInModal.subtotal = existingInModal.qty * existingInModal.price;
        } else {
            state.modalParticipantItems.push({
                item_id: targetItem.id,
                name: targetItem.name,
                qty: 1,
                price: targetItem.price,
                subtotal: targetItem.price,
            });
        }

        renderModalDrawers();
    }

    function recalculateModalSummary() {
        const subtotal = state.modalParticipantItems.reduce((acc, it) => acc + (it.qty * it.price), 0);
        const allItemsSubtotal = state.billInfo.subtotal || 1;
        const prop = allItemsSubtotal > 0 ? (subtotal / allItemsSubtotal) : 0;

        const taxShare = state.billInfo.tax * prop;
        const serviceShare = state.billInfo.service * prop;
        const discountShare = state.billInfo.discount * prop;
        const total = subtotal + taxShare + serviceShare - discountShare;

        modalSubtotalText.textContent = formatRupiah(subtotal);
        modalTaxText.textContent = formatRupiah(taxShare);
        modalServiceText.textContent = formatRupiah(serviceShare);
        modalDiscountText.textContent = `-${formatRupiah(discountShare)}`;
        modalTotalText.textContent = formatRupiah(total);
    }

    if (btnSaveParticipant) {
        btnSaveParticipant.addEventListener('click', () => {
            const name = modalParticipantName.value.trim();
            if (!name) {
                showToast("Nama peserta tidak boleh kosong.", 'warning');
                return;
            }

            if (state.modalParticipantItems.length === 0) {
                showToast("Pilih minimal 1 pesanan untuk peserta ini.", 'warning');
                return;
            }

            // Validasi kuantitas tidak melebihi sisa pembelian
            const allocated = calculateAllocatedQuantities(state.editingParticipantIndex);
            for (let pIt of state.modalParticipantItems) {
                const orig = state.items.find(i => i.id === pIt.item_id);
                if (orig) {
                    const alreadyAlloc = allocated[orig.id] || 0;
                    if (alreadyAlloc + pIt.qty > orig.qty + 0.0001) {
                        showToast(`Porsi "${pIt.name}" melebihi jumlah yang tersedia pada struk.`, 'danger');
                        return;
                    }
                }
            }

            const pData = {
                id: state.editingParticipantIndex >= 0 ? state.participants[state.editingParticipantIndex].id : (state.participants.length + 1),
                name: name,
                items: state.modalParticipantItems,
            };

            if (state.editingParticipantIndex >= 0) {
                state.participants[state.editingParticipantIndex] = pData;
            } else {
                state.participants.push(pData);
            }

            closeModal();
            renderParticipantsList();
            renderAllocationStatus();
            showToast(`Pesanan untuk ${name} berhasil disimpan!`, 'success');
        });
    }

    if (btnBackToOcr) {
        btnBackToOcr.addEventListener('click', () => {
            goToStep(2);
        });
    }

    if (btnFinishToReview) {
        btnFinishToReview.addEventListener('click', (e) => {
            const isCompleted = renderAllocationStatus();
            if (btnFinishToReview.disabled || !isCompleted) {
                e.preventDefault();
                if (state.participants.length === 0) {
                    showToast("Harus ada minimal satu orang peserta.", 'warning');
                } else {
                    showToast("Alokasi belum selesai. Bagikan seluruh menu struk ke peserta sampai tuntas terlebih dahulu.", 'warning');
                }
                return;
            }

            initStepReview();
            goToStep(4);
        });
    }

    // ==========================================
    // STEP 4: REVIEW & HASIL SPLITBILL
    // ==========================================
    const reviewRestoName = document.getElementById('review-resto-name');
    const reviewGrandTotal = document.getElementById('review-grand-total');
    const reviewPaxCount = document.getElementById('review-pax-count');
    const reviewTax = document.getElementById('review-tax');
    const reviewService = document.getElementById('review-service');
    const reviewDiscount = document.getElementById('review-discount');
    const reviewParticipantsGrid = document.getElementById('review-participants-grid');
    const btnBackToSplit = document.getElementById('btn-back-to-split');
    const btnSaveBill = document.getElementById('btn-save-bill');
    const saveLoading = document.getElementById('save-loading');
    const saveBtnText = document.getElementById('save-btn-text');

    function initStepReview() {
        if (state.mode === 'bagi-rata') {
            const { grandTotal, count, baseAmount, remainder } = calculateEqualSplitAmounts();
            reviewRestoName.textContent = state.billInfo.restaurant_name || 'Restoran / Kafe';
            reviewGrandTotal.textContent = formatRupiah(grandTotal);
            reviewPaxCount.textContent = `${count} Orang (Bagi Rata)`;
            reviewTax.textContent = formatRupiah(state.billInfo.tax);
            reviewService.textContent = formatRupiah(state.billInfo.service);
            reviewDiscount.textContent = formatRupiah(state.billInfo.discount);

            reviewParticipantsGrid.innerHTML = '';
            state.equalSplit.participants.forEach((p, idx) => {
                const pTotal = idx < remainder ? (baseAmount + 1) : baseAmount;
                const pTax = count > 0 ? Math.round(state.billInfo.tax / count) : 0;
                const pService = count > 0 ? Math.round(state.billInfo.service / count) : 0;
                const pDiscount = count > 0 ? Math.round(state.billInfo.discount / count) : 0;
                const pSubtotal = pTotal - pTax - pService + pDiscount;

                const card = document.createElement('div');
                card.className = 'participant-card';
                card.innerHTML = `
                    <div>
                        <div class="participant-name">${escapeHtml(p.name)}</div>
                        <ul class="participant-items-list">
                            <li>
                                <span>1x Porsi Bagi Rata</span>
                                <span>${formatRupiah(pSubtotal)}</span>
                            </li>
                        </ul>
                    </div>
                    <div>
                        <div class="participant-breakdown">
                            <div class="participant-breakdown-row">
                                <span>Subtotal:</span>
                                <span>${formatRupiah(pSubtotal)}</span>
                            </div>
                            ${state.billInfo.tax > 0 ? `
                            <div class="participant-breakdown-row">
                                <span>Pajak (proporsional):</span>
                                <span>${formatRupiah(pTax)}</span>
                            </div>` : ''}
                            ${state.billInfo.service > 0 ? `
                            <div class="participant-breakdown-row">
                                <span>Service Charge:</span>
                                <span>${formatRupiah(pService)}</span>
                            </div>` : ''}
                            ${state.billInfo.discount > 0 ? `
                            <div class="participant-breakdown-row">
                                <span>Diskon:</span>
                                <span>-${formatRupiah(pDiscount)}</span>
                            </div>` : ''}
                        </div>
                        <div class="participant-total-highlight">
                            <span style="font-size:0.9rem;font-weight:600;color:var(--text-muted);">Total Bayar</span>
                            <span>${formatRupiah(pTotal)}</span>
                        </div>
                    </div>
                `;
                reviewParticipantsGrid.appendChild(card);
            });
            return;
        }

        reviewRestoName.textContent = state.billInfo.restaurant_name;
        reviewGrandTotal.textContent = formatRupiah(state.billInfo.grand_total);
        reviewPaxCount.textContent = `${state.participants.length} Orang`;
        reviewTax.textContent = formatRupiah(state.billInfo.tax);
        reviewService.textContent = formatRupiah(state.billInfo.service);
        reviewDiscount.textContent = formatRupiah(state.billInfo.discount);

        renderReviewGrid();
    }

    function renderReviewGrid() {
        reviewParticipantsGrid.innerHTML = '';

        const totalParticipantsSubtotal = state.participants.reduce((acc, p) => {
            return acc + p.items.reduce((sum, it) => sum + (it.qty * it.price), 0);
        }, 0);

        state.participants.forEach(p => {
            const pSubtotal = p.items.reduce((acc, it) => acc + (it.qty * it.price), 0);
            const prop = totalParticipantsSubtotal > 0 ? (pSubtotal / totalParticipantsSubtotal) : 0;

            const pTax = Math.round(state.billInfo.tax * prop);
            const pService = Math.round(state.billInfo.service * prop);
            const pDiscount = Math.round(state.billInfo.discount * prop);
            const pTotal = Math.round(pSubtotal + pTax + pService - pDiscount);

            const card = document.createElement('div');
            card.className = 'participant-card';

            let itemsListHtml = '';
            p.items.forEach(it => {
                itemsListHtml += `
                    <li>
                        <span>${it.qty}x ${escapeHtml(it.name)}</span>
                        <span>${formatRupiah(it.qty * it.price)}</span>
                    </li>
                `;
            });

            card.innerHTML = `
                <div>
                    <div class="participant-name">${escapeHtml(p.name)}</div>
                    <ul class="participant-items-list">
                        ${itemsListHtml}
                    </ul>
                </div>
                <div>
                    <div class="participant-breakdown">
                        <div class="participant-breakdown-row">
                            <span>Subtotal:</span>
                            <span>${formatRupiah(pSubtotal)}</span>
                        </div>
                        ${state.billInfo.tax > 0 ? `
                        <div class="participant-breakdown-row">
                            <span>Pajak (proporsional):</span>
                            <span>${formatRupiah(pTax)}</span>
                        </div>` : ''}
                        ${state.billInfo.service > 0 ? `
                        <div class="participant-breakdown-row">
                            <span>Service Charge:</span>
                            <span>${formatRupiah(pService)}</span>
                        </div>` : ''}
                        ${state.billInfo.discount > 0 ? `
                        <div class="participant-breakdown-row">
                            <span>Diskon:</span>
                            <span>-${formatRupiah(pDiscount)}</span>
                        </div>` : ''}
                    </div>
                    <div class="participant-total-highlight">
                        <span style="font-size:0.9rem;font-weight:600;color:var(--text-muted);">Total Bayar</span>
                        <span>${formatRupiah(pTotal)}</span>
                    </div>
                </div>
            `;
            reviewParticipantsGrid.appendChild(card);
        });
    }

    if (btnBackToSplit) {
        btnBackToSplit.addEventListener('click', () => {
            goToStep(3);
        });
    }

    // Tombol "Simpan Hasil" ke Django Cache
    if (btnSaveBill) {
        const originalSaveBtnHtml = btnSaveBill.innerHTML;

        btnSaveBill.addEventListener('click', async () => {
            btnSaveBill.disabled = true;
            btnSaveBill.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; gap: 0.5rem;">
                    <div class="spinner"></div>
                    <span>Loading...</span>
                </div>
            `;

            const payload = state.mode === 'bagi-rata' ? {
                split_mode: 'equal',
                participant_count: state.equalSplit.count,
                participant_names: state.equalSplit.participants.map(p => p.name),
                bill_info: state.billInfo,
                items: state.items,
            } : {
                split_mode: 'itemized',
                bill_info: state.billInfo,
                items: state.items,
                participants: state.participants,
            };

            try {
                const response = await fetch('/api/simpan/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify(payload),
                });

                const result = await response.json();

                if (!response.ok || result.status !== 'success') {
                    throw new Error(result.message || 'Gagal menyimpan hasil splitbill.');
                }

                // Sukses tersimpan di cache
                showToast("Splitbill berhasil disimpan!", 'success');

                // Perbarui sisa kuota jika ada di navbar
                if (result.remaining_quota !== undefined) {
                    updateNavbarQuotaBadge(result.remaining_quota);
                }

                initStepConfirmation(result);
                goToStep(5);
            } catch (err) {
                showToast(err.message || "Gagal menyimpan ke server.", 'danger');
            } finally {
                btnSaveBill.disabled = false;
                btnSaveBill.innerHTML = originalSaveBtnHtml;
            }
        });
    }

    // ==========================================
    // STEP 5: KONFIRMASI SUKSES & URL BERBAGI
    // ==========================================
    const sharedUrlInput = document.getElementById('shared-bill-url');
    const btnCopyUrl = document.getElementById('btn-copy-shared-url');
    const btnOpenBill = document.getElementById('btn-open-shared-bill');

    function initStepConfirmation(result) {
        const fullUrl = window.location.origin + result.bill_url;
        sharedUrlInput.value = fullUrl;

        btnCopyUrl.onclick = () => {
            copyToClipboard(fullUrl, "URL tagihan berhasil disalin! Silakan bagikan ke grup teman-teman.");
        };

        btnOpenBill.href = result.bill_url;

        // Mulai countdown 10 menit
        initLiveCountdown('confirmation-countdown', result.ttl_seconds || 600, () => {
            showToast("Waktu penyimpanan tagihan ini telah habis.", 'warning');
        });
    }
});

