"""
URL configuration for Smart Splitbill project.
"""

from django.urls import path, include

urlpatterns = [
    path('', include('splitbill.urls')),
]

handler404 = 'splitbill.error_views.custom_404_view'
handler500 = 'splitbill.error_views.custom_500_view'

