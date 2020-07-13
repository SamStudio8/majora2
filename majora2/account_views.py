from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.contrib.auth.decorators import login_required

from django.db.models import Q
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone

from . import models
from . import util
from . import forms
from . import signals
from tatl import signals as tsignals

import json
import uuid

from two_factor.utils import default_device

def generate_username(cleaned_data):
    proposed_username = "%s%s%s" % (settings.USER_PREFIX, cleaned_data["last_name"].replace(' ', '').lower(), cleaned_data["first_name"][0].lower())

    potentially_existing_profiles = models.Profile.objects.filter(user__username__startswith=proposed_username)
    if potentially_existing_profiles.count() > 0:
        for existing_profile in potentially_existing_profiles:
            if existing_profile.user.email == cleaned_data.get("email"):
                return proposed_username # return this username and cause the form to error out on duplicate

        # this person is probably a different person with the same name as someone else
        #  or someone who cannot keep track of their email addresses, create a new incremented username anyway
        proposed_username = "%s%d" % (proposed_username, potentially_existing_profiles.count()+1)
    return proposed_username

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
def form_account(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    from django.forms.models import model_to_dict

    if not hasattr(request.user, "profile"):
        return HttpResponseBadRequest() # bye

    init = model_to_dict(request.user)
    init["organisation"] = request.user.profile.institute.code
    init["ssh_key"] = request.user.profile.ssh_key

    if request.method == "POST":
        form = forms.AccountForm(request.POST, initial=init)
        if form.is_valid():
            u = request.user
            u.first_name = form.cleaned_data['first_name']
            u.last_name = form.cleaned_data['last_name']
            u.email = form.cleaned_data['email']
            u.save()

            p = request.user.profile
            p.ssh_key = form.cleaned_data['ssh_key']
            p.save()

            return render(request, 'accounts/institute_success.html')
    else:
        form = forms.AccountForm(initial=init)
    return render(request, 'forms/account.html', {'form': form})

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
                        '1' if user.profile.is_site_approved else '0',
                        '1' if user.is_active else '0',
                        user.username,
                        user.first_name,
                        user.last_name,
                        user.email,
                        user.profile.institute.code
                    ]))
            return HttpResponse("\n".join(keys), content_type="text/plain")
    return HttpResponseBadRequest() # bye

@login_required
def api_keys(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    generated = models.ProfileAPIKey.objects.filter(profile=request.user.profile)
    available = models.ProfileAPIKeyDefinition.objects.filter(Q(permission__isnull=True) | Q(permission__in=request.user.user_permissions.all())).exclude(id__in=generated.values('key_definition__id'))

    return render(request, 'api_keys.html', {
        'user': request.user,
        'available': available,
        'generated': generated,
    })

@login_required
def api_keys_activate(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    if request.method != 'POST':
        return HttpResponseBadRequest() # bye

    key_name = request.POST.get("key_name")
    if not key_name:
        return HttpResponseBadRequest() # bye
    key_def = get_object_or_404(models.ProfileAPIKeyDefinition, key_name=key_name)

    # Check user has permission to activate the key
    if key_def.permission:
        if not request.user.has_perm('majora2.%s' % key_def.permission.codename):
            #TODO should probably report this to tatl
            return HttpResponseBadRequest() # bye

    k, key_is_new = models.ProfileAPIKey.objects.get_or_create(profile=request.user.profile, key_definition=key_def)
    k.key = uuid.uuid4()
    now = timezone.now()
    k.validity_start = now
    k.validity_end = now + key_def.lifespan
    k.save()

    return redirect(reverse('api_keys'))

@login_required
def list_site_profiles(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    if not hasattr(request.user, "profile"):
        return HttpResponseBadRequest() # bye
    if not request.user.has_perm("majora2.can_approve_profiles"):
        return HttpResponseBadRequest() # bye

    if request.method == 'POST':
        profile_id_to_approve = request.POST.get("profile")
        if profile_id_to_approve:
            try:
                profile_to_approve = models.Profile.objects.get(pk=profile_id_to_approve)
            except:
                return HttpResponseBadRequest() # bye

            if profile_to_approve:
                if profile_to_approve.institute != request.user.profile.institute:
                    return HttpResponseBadRequest() # bye

                profile_to_approve.is_site_approved = True
                profile_to_approve.save()
                signals.site_approved_registration.send(
                        sender=request,
                        approver=request.user,
                        approved_profile=profile_to_approve
                )


    # Render the list regardless of what the form did
    active_site_profiles = models.Profile.objects.filter(institute=request.user.profile.institute, is_site_approved=True)
    inactive_site_profiles = models.Profile.objects.filter(institute=request.user.profile.institute, is_site_approved=False)
    return render(request, 'site_profiles.html', {
        'user': request.user,
        'org': request.user.profile.institute,
        'active_profiles': active_site_profiles,
        'inactive_profiles': inactive_site_profiles,
    })

@login_required
def agreements(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    signed = models.ProfileAgreement.objects.filter(profile=request.user.profile)
    available = models.ProfileAgreementDefinition.objects.exclude(id__in=signed.values('agreement__id'))

    return render(request, 'agreements.html', {
        'user': request.user,
        'available': available,
        'signed': signed,
    })

@login_required
def view_agreement(request, slug):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    if not hasattr(request.user, "profile"):
        return HttpResponseBadRequest() # bye

    agreement = None
    signature = None
    if request.method == 'POST':
        # SIGNING AGREEMENT
        pass
    else:
        # VIEWING AGREEMENT
        try:
            signature = models.ProfileAgreement.objects.get(agreement_slug=slug, profile=request.user.profile)
            agreement = signature.agreement
            signed = True
        except:
            try:
                agreement = models.ProfileAgreementDefinition.objects.get(slug=slug)
                signed = False
            except:
                return HttpResponseBadRequest() # bye

    return render(request, 'view_agreement.html', {
        'user': request.user,
        'agreement': agreement,
        'signature': signature,
        'signed': signed,
    })
