from django.shortcuts import render

from .util import django_2fa_mixin_hack

def oauth2_callback(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    return render(request, 'oauth2_provider/authorized-oob.html', {
        "code": request.GET.get("code"),
        "state": request.GET.get("state"),
        "error": request.GET.get("error"),
    })
