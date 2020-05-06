from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.contrib.auth.decorators import login_required

from django.contrib.auth.models import User
from django.conf import settings

from . import models
from . import util
from . import forms
from . import signals

import json

from two_factor.utils import default_device

def generate_username(cleaned_data):
    return "%s%s%s" % (settings.USER_PREFIX, cleaned_data["last_name"].replace(' ', '').lower(), cleaned_data["first_name"][0].lower())

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

@sensitive_post_parameters('password', 'password2')
def form_register(request):
    if request.method == "POST":
        form = forms.RegistrationForm(request.POST)
        if form.is_valid():
            u = User()
            u.username = generate_username(form.cleaned_data)
            u.first_name = form.cleaned_data['first_name']
            u.last_name = form.cleaned_data['last_name']
            u.email = form.cleaned_data['email']
            u.set_password(form.cleaned_data["password2"])
            u.is_active = False
            u.save()

            p = models.Profile(user=u)
            p.institute = form.cleaned_data['organisation']
            p.ssh_key = form.cleaned_data['ssh_key']
            p.save()

            signals.new_registration.send(sender=request, username=u.username, first_name=u.first_name, last_name=u.last_name, email=u.email, organisation=p.institute.name)
            return render(request, 'accounts/register_success.html')
    else:
        form = forms.RegistrationForm()
    return render(request, 'forms/register.html', {'form': form})

@login_required
def form_institute(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    from django.forms.models import model_to_dict

    if not hasattr(request.user, "profile"):
        return HttpResponseBadRequest() # bye

    org = get_object_or_404(models.Institute, code=request.user.profile.institute.code)

    init = model_to_dict(org)
    if request.method == "POST":
        form = forms.InstituteForm(request.POST, initial=init)
        if form.is_valid():
            org.gisaid_opted = form.cleaned_data.get("gisaid_opted")
            org.gisaid_user = form.cleaned_data.get("gisaid_user")
            org.gisaid_mail = form.cleaned_data.get("gisaid_mail")
            org.gisaid_lab_name = form.cleaned_data.get("gisaid_lab_name")
            org.gisaid_lab_addr = form.cleaned_data.get("gisaid_lab_addr")
            org.gisaid_list = form.cleaned_data.get("gisaid_list")
            org.save()
            return render(request, 'accounts/institute_success.html')
    else:
        form = forms.InstituteForm(initial=init)
    return render(request, 'forms/institute.html', {'form': form})


@csrf_exempt
def list_ssh_keys(request, username=None):

    token = request.META.get("HTTP_MAJORA_TOKEN")
    if token and len(token) > 1:
        if models.Profile.objects.filter(api_key=token, user__is_active=True, user__is_staff=True).count() > 0:
            # If at least one token exists, that seems good enough
            keys = []
            for user in User.objects.all():
                if username:
                    if user.username != username:
                        continue
                if hasattr(user, "profile"):
                    if user.profile.ssh_key and user.profile.ssh_key.startswith("ssh"):
                        if not username and not user.is_active:
                            continue # dont show unapproved users in big list
                        keys.append(user.profile.ssh_key)
            return HttpResponse("\n".join(keys), content_type="text/plain")
    return HttpResponseBadRequest() # bye

@csrf_exempt
def list_user_names(request):

    token = request.META.get("HTTP_MAJORA_TOKEN")
    if token and len(token) > 1:
        if models.Profile.objects.filter(api_key=token, user__is_active=True, user__is_staff=True).count() > 0:
            # If at least one token exists, that seems good enough
            keys = []
            for user in User.objects.all():
                if hasattr(user, "profile"):
                    keys.append("\t".join([
                        '1' if user.is_active else '0',
                        user.username,
                        user.first_name,
                        user.last_name,
                        user.email,
                        user.profile.institute.code
                    ]))
            return HttpResponse("\n".join(keys), content_type="text/plain")
    return HttpResponseBadRequest() # bye
