"""
Views untuk Smart Splitbill.
Dashboard, alur pembuatan splitbill, API OCR, API simpan cache TTL, dan detail tagihan read-only.
"""

import json
import logging
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout

from splitbill.services import (
    bill_cache_service,
    ocr_receipt_service,
    calculation_service,
    rate_limiter
)
from splitbill.validators import validate_receipt_file, validate_bill_submission
from splitbill.utils import format_rupiah

logger = logging.getLogger(__name__)


@require_GET
@ensure_csrf_cookie
def index(request):
    """
    Halaman Utama / Dashboard.
    Menampilkan riwayat splitbill aktif yang dibuat oleh sesi pengguna,
    serta sisa kuota OCR harian.
    """
    active_bills = bill_cache_service.get_user_active_bills(request.session)
    is_admin = request.user.is_authenticated and (request.user.is_staff or request.user.username == 'admin')
    if is_admin:
        is_allowed = True
        remaining_quota = 'Unlimited'
    else:
        is_allowed, used_count, remaining_quota = rate_limiter.get_status(request)

    context = {
        'active_bills': active_bills,
        'has_active_bills': len(active_bills) > 0,
        'remaining_quota': remaining_quota,
        'daily_limit': rate_limiter.daily_limit,
        'is_admin': is_admin,
    }
    return render(request, 'splitbill/index.html', context)


@require_GET
@ensure_csrf_cookie
def create_bill(request):
    """
    Halaman Pembuatan Splitbill Baru.
    Menyediakan interface wizard: Upload Struk -> Form OCR -> Pembagian Peserta -> Review -> Simpan.
    """
    is_admin = request.user.is_authenticated and (request.user.is_staff or request.user.username == 'admin')
    if is_admin:
        is_allowed = True
        remaining_quota = 'Unlimited'
    else:
        is_allowed, used_count, remaining_quota = rate_limiter.get_status(request)

    context = {
        'remaining_quota': remaining_quota,
        'daily_limit': rate_limiter.daily_limit,
        'is_ocr_allowed': is_allowed,
        'is_admin': is_admin,
    }
    return render(request, 'splitbill/create.html', context)


@require_POST
def process_ocr_api(request):
    """
    API Pemrosesan OCR Struk dengan Gemini Flash API.
    1. Validasi kuota harian personal (5x/hari), dilewati jika akun admin/pengembang.
    2. Validasi file gambar struk.
    3. Ekstraksi informasi via Gemini Flash API (dengan Structured Output).
    4. Jika kuota habis (baik kuota personal maupun kuota AI model),
       mengembalikan pesan 'kuota 1 hari sudah habis see you besok'.
    """
    # 1. Periksa Kuota OCR Personal (Rate Limiter IP)
    is_admin = request.user.is_authenticated and (request.user.is_staff or request.user.username == 'admin')
    if not is_admin:
        is_allowed, current_count, remaining = rate_limiter.get_status(request)
        if not is_allowed:
            return JsonResponse({
                'status': 'error',
                'message': 'kuota 1 hari sudah habis see you besok',
                'remaining_quota': 0,
            }, status=429)
    else:
        remaining = 'Unlimited'

    # 2. Periksa Keberadaan & Validasi File
    if 'receipt_image' not in request.FILES:
        return JsonResponse({
            'status': 'error',
            'message': 'Harap pilih atau potret foto struk pembayaran terlebih dahulu.'
        }, status=400)

    uploaded_file = request.FILES['receipt_image']
    is_valid, validation_err = validate_receipt_file(uploaded_file)
    if not is_valid:
        return JsonResponse({
            'status': 'error',
            'message': validation_err
        }, status=400)

    # 3. Proses OCR dengan Gemini Flash API
    try:
        extracted_data = ocr_receipt_service.process_receipt_image(uploaded_file)

        # Kuota baru akan dikurangi saat pengguna menyelesaikan dan menyimpan tagihan (Step 4),
        # sehingga jika dibatalkan, refresh, atau keluar di tengah jalan, kuota tetap utuh.
        return JsonResponse({
            'status': 'success',
            'data': extracted_data,
            'remaining_quota': remaining,
        })
    except Exception as e:
        logger.error(f"Kesalahan internal saat memproses OCR: {e}", exc_info=True)
        err_str = str(e).lower()

        # Deteksi jika server Google / model AI sedang sibuk (503 / high demand / semua model gagal)
        if "server sedang sibuk" in err_str or any(k in err_str for k in ["503", "unavailable", "server google sedang sibuk", "high demand", "semua model"]):
            return JsonResponse({
                'status': 'error',
                'message': 'server sedang sibuk',
            }, status=503)

        # Deteksi jika kuota model AI habis (429 / resource exhausted)
        if "kuota 1 hari sudah habis see you besok" in err_str or any(k in err_str for k in ["429", "resource_exhausted", "quota", "kuota"]):
            return JsonResponse({
                'status': 'error',
                'message': 'kuota 1 hari sudah habis see you besok',
                'remaining_quota': 0,
            }, status=429)

        return JsonResponse({
            'status': 'error',
            'message': f'Terjadi kendala saat membaca struk: {str(e)}',
        }, status=500)


@require_POST
def save_bill_api(request):
    """
    API Penyimpanan Tagihan ke Cache dengan TTL 600 detik (10 menit).
    Menerima data JSON perhitungan, memvalidasi alokasi, menghitung pembulatan Rupiah,
    dan menghasilkan token URL unik.
    """
    try:
        body = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({
            'status': 'error',
            'message': 'Format data JSON tidak valid.'
        }, status=400)

    # Periksa kuota sebelum simpan (admin memiliki kuota Unlimited)
    is_admin = request.user.is_authenticated and (request.user.is_staff or request.user.username == 'admin')
    if not is_admin:
        is_allowed, _, remaining = rate_limiter.get_status(request)
        if not is_allowed:
            return JsonResponse({
                'status': 'error',
                'message': 'kuota 1 hari sudah habis see you besok',
                'remaining_quota': 0,
            }, status=429)

    # Validasi struktur formulir
    is_valid_form, form_errors = validate_bill_submission(body)
    if not is_valid_form:
        return JsonResponse({
            'status': 'error',
            'message': 'Validasi formulir gagal: ' + '; '.join(form_errors),
            'errors': form_errors,
        }, status=400)

    split_mode = body.get('split_mode', 'itemized')
    bill_info = body.get('bill_info', {})
    items = body.get('items', [])
    participants = body.get('participants', [])

    if split_mode == 'equal':
        participant_count = int(body.get('participant_count') or len(participants) or 1)
        participant_names = body.get('participant_names')
        if not participant_names and participants:
            participant_names = [p.get('name') for p in participants if isinstance(p, dict) and p.get('name')]

        try:
            calculated_data = calculation_service.calculate_equal_split(
                bill_info=bill_info,
                participant_count=participant_count,
                participant_names=participant_names,
                items=items
            )
        except Exception as e:
            logger.error(f"Gagal melakukan kalkulasi bagi rata: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Terjadi kesalahan saat menghitung bagi rata.'
            }, status=500)
    else:
        # Validasi alokasi seluruh item
        is_allocated, unallocated_items, alloc_errors = calculation_service.validate_allocation(items, participants)
        if not is_allocated:
            return JsonResponse({
                'status': 'error',
                'message': 'Pembagian item belum tuntas: ' + '; '.join(alloc_errors),
                'unallocated_items': unallocated_items,
                'errors': alloc_errors,
            }, status=400)

        # Hitung final kalkulasi dengan Largest Remainder Method
        try:
            calculated_data = calculation_service.calculate_splitbill(bill_info, items, participants)
        except Exception as e:
            logger.error(f"Gagal melakukan kalkulasi splitbill: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Terjadi kesalahan saat menghitung rincian tagihan.'
            }, status=500)

    # Simpan ke cache dengan TTL 600 detik
    token = bill_cache_service.save_bill(calculated_data)

    # Kaitkan ke sesi pengguna agar riwayat aktif muncul di dashboard
    bill_cache_service.attach_bill_to_session(request.session, token)

    # Konsumsi 1 kuota pemrosesan saat tagihan final berhasil disimpan
    if is_admin:
        new_remaining = 'Unlimited'
    else:
        allowed, new_remaining, _ = rate_limiter.consume_quota(request)

    bill_url = f"/tagihan/{token}"
    return JsonResponse({
        'status': 'success',
        'token': token,
        'bill_url': bill_url,
        'ttl_seconds': 600,
        'remaining_quota': new_remaining,
        'message': 'Splitbill berhasil disimpan!',
    })


@require_GET
def bill_detail(request, token: str):
    """
    Halaman Detail Tagihan / Shared Bill (/tagihan/<token>).
    Read-only. Siapa pun yang memiliki URL dapat melihat selama belum kedaluwarsa.
    Jika tidak ditemukan atau kedaluwarsa, tampilkan halaman khusus yang informatif dan ramah.
    """
    bill = bill_cache_service.get_bill(token)
    if not bill:
        # Tampilkan template expired dengan HTTP 404 yang ramah
        return render(request, 'splitbill/expired.html', {'token': token}, status=404)

    # Bangun rincian teks ringkas untuk tombol "Salin ke WhatsApp"
    is_equal_split = bill.get('split_mode') == 'equal'
    mode_suffix = " (Bagi Rata)" if is_equal_split else ""
    wa_lines = [
        f"🧾 *Smart Splitbill{mode_suffix} - {bill.get('restaurant_name')}*",
        f"🗓 Tanggal: {bill.get('transaction_date') or bill.get('created_at_str')}",
        f"💰 Total Tagihan: {bill.get('grand_total_formatted')}",
        "",
        "👥 *Rincian Pembayaran Per Orang:*"
    ]
    for p in bill.get('participants', []):
        wa_lines.append(f"• *{p.get('name')}*: {p.get('total_formatted')}")
        if not is_equal_split:
            for it in p.get('items', []):
                wa_lines.append(f"   - {it.get('qty')}x {it.get('name')} ({it.get('subtotal_formatted')})")

    wa_lines.append("")
    wa_lines.append(f"🔗 Detail lengkap: {request.build_absolute_uri()}")
    wa_lines.append("⏱ _Link berlaku 10 menit sejak disimpan._")
    share_text = "\n".join(wa_lines)

    context = {
        'bill': bill,
        'share_text': share_text,
        'token': token,
    }
    return render(request, 'splitbill/detail.html', context)


@require_GET
def bill_status_api(request, token: str):
    """
    API ringan untuk mengecek sisa waktu kedaluwarsa tagihan secara realtime.
    """
    bill = bill_cache_service.get_bill(token)
    if not bill:
        return JsonResponse({
            'active': False,
            'remaining_seconds': 0,
            'message': 'Tagihan tidak ditemukan atau sudah kedaluwarsa.'
        }, status=404)

    return JsonResponse({
        'active': True,
        'remaining_seconds': bill.get('remaining_seconds', 0),
        'restaurant_name': bill.get('restaurant_name'),
        'grand_total_formatted': bill.get('grand_total_formatted'),
    })


@require_POST
def login_api(request):
    """
    API Login untuk Pengembang / Admin.
    Menerima username dan password via JSON atau form-data.
    """
    try:
        if request.content_type == 'application/json':
            body = json.loads(request.body.decode('utf-8'))
            username = body.get('username', '').strip()
            password = body.get('password', '').strip()
        else:
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '').strip()
    except Exception:
        return JsonResponse({
            'status': 'error',
            'message': 'Format data login tidak valid.'
        }, status=400)

    if not username or not password:
        return JsonResponse({
            'status': 'error',
            'message': 'Username dan password wajib diisi.'
        }, status=400)

    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        return JsonResponse({
            'status': 'success',
            'message': f'Login berhasil! Selamat datang Admin {user.username}.',
            'user': {
                'username': user.username,
                'is_staff': user.is_staff,
            }
        })
    else:
        return JsonResponse({
            'status': 'error',
            'message': 'Username atau password admin salah.'
        }, status=401)


@require_POST
def logout_api(request):
    """
    API Logout Admin / Pengembang.
    """
    logout(request)
    return JsonResponse({
        'status': 'success',
        'message': 'Anda telah keluar dari mode admin.'
    })


@require_POST
def admin_reset_quota_api(request):
    """
    API Reset Kuota Khusus Admin / Pengembang.
    Hanya dapat dieksekusi jika pengguna telah terautentikasi sebagai admin.
    """
    if not (request.user.is_authenticated and (request.user.is_staff or request.user.username == 'admin')):
        return JsonResponse({
            'status': 'error',
            'message': 'Akses ditolak: Hanya admin yang diizinkan mereset kuota.'
        }, status=403)

    rate_limiter.reset_quota(request)
    return JsonResponse({
        'status': 'success',
        'message': f'Kuota berhasil direset ke {rate_limiter.daily_limit}!',
        'remaining_quota': rate_limiter.daily_limit,
    })
