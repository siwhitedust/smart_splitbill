"""
Routing URL untuk aplikasi splitbill.
"""

from django.conf import settings
from django.urls import path
from splitbill import views
from splitbill.error_views import fake_admin_404_view

app_name = 'splitbill'

# Ambil slug path admin rahasia dari Django settings (default: portal-rahasia-admin)
admin_slug = getattr(settings, 'ADMIN_URL_PATH', 'portal-rahasia-admin').strip('/')
if not admin_slug:
    admin_slug = 'portal-rahasia-admin'

urlpatterns = [
    path('', views.index, name='index'),
    path('buat/', views.create_bill, name='create'),
    path('tagihan/<str:token>', views.bill_detail, name='bill_detail'),
    path('tagihan/<str:token>/', views.bill_detail, name='bill_detail_slash'),
    path('api/ocr/', views.process_ocr_api, name='api_ocr'),
    path('api/simpan/', views.save_bill_api, name='api_simpan'),
    path('api/status/<str:token>/', views.bill_status_api, name='api_status'),
    path('api/login/', views.login_api, name='api_login'),
    path('api/logout/', views.logout_api, name='api_logout'),
    path('api/admin/reset-kuota/', views.admin_reset_quota_api, name='api_admin_reset_quota'),

    # URL Rahasia / Spesial Khusus Dashboard Admin
    path(f'{admin_slug}/', views.admin_dashboard, name='admin_dashboard'),

    # API Kontrol Admin
    path('api/admin/reset-all-quota/', views.admin_reset_all_quota_api, name='api_admin_reset_all_quota'),
    path('api/admin/reset-user-quota/', views.admin_reset_user_quota_api, name='api_admin_reset_user_quota'),
    path('api/admin/clear-logs/', views.admin_clear_logs_api, name='api_admin_clear_logs'),
]

# Honeypot / Fake 404 untuk URL umum agar pihak luar mengira admin tidak ada
if admin_slug != 'admin':
    urlpatterns.append(path('admin/', fake_admin_404_view, name='fake_admin_404'))
if admin_slug != 'admin-dashboard':
    urlpatterns.append(path('admin-dashboard/', fake_admin_404_view, name='fake_admin_dashboard_404'))
