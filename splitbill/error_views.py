"""
Handler error kustom untuk Smart Splitbill.
Mencegah server traceback membocorkan informasi internal ke pengguna.
"""

from django.shortcuts import render


def custom_404_view(request, exception=None):
    return render(request, 'splitbill/expired.html', status=404)


def custom_500_view(request):
    return render(request, 'splitbill/expired.html', status=500)

