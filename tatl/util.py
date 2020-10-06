from two_factor.utils import default_device
from django.shortcuts import render, reverse
from django.contrib.auth.views import redirect_to_login

def django_2fa_mixin_hack(request):
    raise_anonymous = False
    if not request.user or not request.user.is_authenticated or \
            (not request.user.is_verified() and default_device(request.user)):
        # If the user has not authenticated raise or redirect to the login
        # page. Also if the user just enabled two-factor authentication and
        # has not yet logged in since should also have the same result. If
        # the user receives a 'you need to enable TFA' by now, he gets
        # confuses as TFA has just been enabled. So we either raise or
        # redirect to the login page.
        if raise_anonymous:
            raise PermissionDenied()
        else:
            return redirect_to_login(request.get_full_path(), reverse('two_factor:login'))
    device = default_device(request.user)

    if not request.user.is_verified():
        if device:
            return redirect_to_login(request.get_full_path(), reverse('two_factor:login'))
        else:
            return render(
                request,
                'two_factor/core/otp_required.html',
                status=403,
            )
