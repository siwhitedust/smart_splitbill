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
// Login / Logout Modal Interactivity
// ==========================================
function initLoginModal() {
    const loginModal = document.getElementById('login-modal');
    const btnOpenLogin = document.getElementById('btn-open-login');
    const btnCloseLoginX = document.getElementById('btn-close-login-modal-x');
    const btnContinue = document.getElementById('btn-continue-without-login');
    const formLogin = document.getElementById('form-login');
    const loginAlertError = document.getElementById('login-alert-error');
    const btnSubmitLogin = document.getElementById('btn-submit-login');
    const btnLogout = document.getElementById('btn-logout');
    const btnAdminResetQuota = document.getElementById('btn-admin-reset-quota');

    const openModal = () => {
        if (!loginModal) return;
        if (loginAlertError) loginAlertError.style.display = 'none';
        loginModal.classList.add('active');
        const usernameInput = document.getElementById('login-username');
        if (usernameInput) setTimeout(() => usernameInput.focus(), 100);
    };

    const closeModal = () => {
        if (!loginModal) return;
        loginModal.classList.remove('active');
    };

    if (btnOpenLogin) btnOpenLogin.addEventListener('click', openModal);
    if (btnCloseLoginX) btnCloseLoginX.addEventListener('click', closeModal);
    if (btnContinue) btnContinue.addEventListener('click', closeModal);
    if (loginModal) {
        loginModal.addEventListener('click', (e) => {
            if (e.target === loginModal) closeModal();
        });
    }

    if (formLogin) {
        formLogin.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('login-username').value.trim();
            const password = document.getElementById('login-password').value.trim();

            if (!username || !password) {
                if (loginAlertError) {
                    loginAlertError.textContent = 'Username dan password wajib diisi.';
                    loginAlertError.style.display = 'block';
                }
                return;
            }

            if (btnSubmitLogin) {
                btnSubmitLogin.disabled = true;
                btnSubmitLogin.innerHTML = '<span>Memverifikasi...</span>';
            }

            try {
                const resp = await fetch('/api/login/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ username, password }),
                });
                const res = await resp.json();
                if (resp.ok && res.status === 'success') {
                    showToast(res.message || 'Login berhasil!', 'success');
                    closeModal();
                    setTimeout(() => window.location.reload(), 400);
                } else {
                    if (loginAlertError) {
                        loginAlertError.textContent = res.message || 'Username atau password salah.';
                        loginAlertError.style.display = 'block';
                    }
                }
            } catch (err) {
                if (loginAlertError) {
                    loginAlertError.textContent = 'Terjadi kesalahan koneksi saat login.';
                    loginAlertError.style.display = 'block';
                }
            } finally {
                if (btnSubmitLogin) {
                    btnSubmitLogin.disabled = false;
                    btnSubmitLogin.innerHTML = '<span>Masuk sebagai Admin</span>';
                }
            }
        });
    }

    if (btnLogout) {
        btnLogout.addEventListener('click', async () => {
            try {
                const resp = await fetch('/api/logout/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });
                if (resp.ok) {
                    showToast('Berhasil logout dari mode admin.', 'info');
                    setTimeout(() => window.location.reload(), 400);
                }
            } catch (err) {
                showToast('Gagal logout.', 'danger');
            }
        });
    }

    if (btnAdminResetQuota) {
        btnAdminResetQuota.addEventListener('click', async () => {
            btnAdminResetQuota.disabled = true;
            try {
                const resp = await fetch('/api/admin/reset-kuota/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                });
                const res = await resp.json();
                if (resp.ok && res.status === 'success') {
                    showToast(res.message || 'Kuota berhasil direset oleh admin!', 'success');
                } else {
                    showToast(res.message || 'Gagal mereset kuota.', 'danger');
                }
            } catch (err) {
                showToast('Koneksi gagal saat mereset kuota.', 'danger');
            } finally {
                btnAdminResetQuota.disabled = false;
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', initLoginModal);



