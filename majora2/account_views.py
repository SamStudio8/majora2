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

def generate_username(cleaned_data):
    return "%s%s%s" % (settings.USER_PREFIX, cleaned_data["last_name"][:8].lower(), cleaned_data["first_name"][0].lower())

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
            return HttpResponse(json.dumps({
                "success": True,
            }), content_type="application/json")
    else:
        form = forms.RegistrationForm()
    return render(request, 'forms/register.html', {'form': form})


@login_required
def list_ssh_keys(request):
    keys = []
    for user in User.objects.all():
        if hasattr(user, "profile"):
            if user.profile.ssh_key and user.profile.ssh_key.startswith("ssh"):
                keys.append(user.profile.ssh_key)
    return HttpResponse("\n".join(keys), content_type="text/plain")
