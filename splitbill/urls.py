"""
Routing URL untuk aplikasi splitbill.
"""

from django.urls import path
from splitbill import views

app_name = 'splitbill'

urlpatterns = [
    path('', views.index, name='index'),
    path('buat/', views.create_bill, name='create'),
    path('tagihan/<str:token>', views.bill_detail, name='bill_detail'),
    path('tagihan/<str:token>/', views.bill_detail, name='bill_detail_slash'),
    path('api/ocr/', views.process_ocr_api, name='api_ocr'),
    path('api/reset-kuota/', views.reset_quota_api, name='api_reset_quota'),
    path('api/simpan/', views.save_bill_api, name='api_simpan'),
    path('api/status/<str:token>/', views.bill_status_api, name='api_status'),
]

