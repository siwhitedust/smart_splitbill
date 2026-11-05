/**
 * Utilitas Umum Smart Splitbill
 * Format Rupiah, Toast notification, Countdown Timer, Clipboard Helper, dan CSRF.
 */

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function formatRupiah(value, withPrefix = true) {
    if (value === null || value === undefined || isNaN(value)) {
        value = 0;
    }
    const num = Math.round(Number(value));
    const formatted = num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return withPrefix ? `Rp${formatted}` : formatted;
}

function parseNumber(value) {
    if (!value) return 0;
    if (typeof value === 'number') return value;
    const clean = value.toString().replace(/[^\d.,\-]/g, '');
    if (clean.includes('.') && clean.includes(',')) {
        return parseFloat(clean.replace(/\./g, '').replace(',', '.')) || 0;
    }
    if (clean.includes(',') && !clean.includes('.')) {
        return parseFloat(clean.replace(',', '.')) || 0;
    }
    return parseFloat(clean) || 0;
}

function showToast(message, type = 'info', duration = 4000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Icon SVG sederhana
    let iconSvg = '';
    if (type === 'success') {
        iconSvg = `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>`;
    } else if (type === 'danger' || type === 'error') {
        iconSvg = `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>`;
    } else {
        iconSvg = `<svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`;
    }

    toast.innerHTML = `
        <span style="display:flex;align-items:center;color:#60a5fa;">${iconSvg}</span>
        <span style="flex:1;">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function escapeHtml(string) {
    if (!string) return '';
    return String(string)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function copyToClipboard(text, successMsg = "Teks berhasil disalin ke clipboard!") {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
            // Fallback untuk browser / insecure context
            const textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            textArea.style.top = "-999999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            document.execCommand('copy');
            textArea.remove();
        }
        showToast(successMsg, 'success');
    } catch (err) {
        showToast("Gagal menyalin teks ke clipboard.", 'danger');
    }
}

function initLiveCountdown(elementOrId, initialSeconds, onExpire) {
    const el = (typeof elementOrId === 'string') ? document.getElementById(elementOrId) : elementOrId;
    if (!el) return;

    let remaining = parseInt(initialSeconds, 10);
    if (isNaN(remaining) || remaining <= 0) {
        el.textContent = "00:00 (Kedaluwarsa)";
        if (typeof onExpire === 'function') onExpire();
        return;
    }

    function updateDisplay() {
        if (remaining <= 0) {
            el.textContent = "00:00 (Kedaluwarsa)";
            clearInterval(timer);
            if (typeof onExpire === 'function') onExpire();
            return;
        }

        const mins = Math.floor(remaining / 60);
        const secs = remaining % 60;
        el.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
        remaining -= 1;
    }

    updateDisplay();
    const timer = setInterval(updateDisplay, 1000);
}

// ==========================================
// Theme Switcher (Dark & Light Mode, Default: Dark)
// ==========================================
function initThemeToggle() {
    const toggleBtn = document.getElementById('theme-toggle-btn');
    if (!toggleBtn) return;

    const getTheme = () => document.documentElement.getAttribute('data-theme') || localStorage.getItem('smart_splitbill_theme') || 'dark';

    const setTheme = (theme) => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('smart_splitbill_theme', theme);
    };

    // Pastikan tema terpasang
    const active = getTheme();
    setTheme(active);

    toggleBtn.addEventListener('click', () => {
        const current = getTheme();
        const next = current === 'dark' ? 'light' : 'dark';
        setTheme(next);
        showToast(next === 'dark' ? 'Mode Gelap diaktifkan' : 'Mode Terang diaktifkan', 'info', 1800);
    });
}

document.addEventListener('DOMContentLoaded', initThemeToggle);

// ==========================================
// Reset Kuota (Khusus Masa Pengembangan / Testing)
// ==========================================
function initResetQuota() {
    const btnReset = document.getElementById('btn-reset-quota');
    if (!btnReset) return;

    btnReset.addEventListener('click', async () => {
        btnReset.disabled = true;
        try {
            const resp = await fetch('/api/reset-kuota/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                },
            });
            const res = await resp.json();
            if (resp.ok && res.status === 'success') {
                showToast(res.message || 'Kuota berhasil direset!', 'success');
                // Perbarui tampilan badge kuota di navbar
                const quotaBadgeEl = document.querySelector('.quota-badge strong');
                const quotaIndicator = document.querySelector('.quota-indicator');
                if (quotaBadgeEl) {
                    quotaBadgeEl.textContent = `${res.remaining_quota}/${res.daily_limit || 5}`;
                }
                if (quotaIndicator) {
                    quotaIndicator.className = 'quota-indicator';
                }
            } else {
                showToast('Gagal mereset kuota.', 'danger');
            }
        } catch (err) {
            showToast('Koneksi gagal saat mereset kuota.', 'danger');
        } finally {
            btnReset.disabled = false;
        }
    });
}

document.addEventListener('DOMContentLoaded', initResetQuota);


