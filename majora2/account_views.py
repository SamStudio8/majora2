from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict

from django.db.models import Q
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone

from . import models
from . import util
from . import forms
from . import signals
from tatl.util import django_2fa_mixin_hack

import json
import uuid

def generate_username(cleaned_data):
    last_name = cleaned_data["last_name"].replace(' ', '').lower()
    last_name = last_name[:(settings.USER_LEN_BEFORE_NUM - (len(settings.USER_PREFIX) + 1))]

    proposed_username = "%s%s%s" % (settings.USER_PREFIX, last_name, cleaned_data["first_name"][0].lower())
    proposed_username = proposed_username[:settings.USER_LEN_BEFORE_NUM]

    potentially_existing_profiles = models.Profile.objects.filter(user__username__startswith=proposed_username)
    if potentially_existing_profiles.count() > 0:
        for existing_profile in potentially_existing_profiles:
            if existing_profile.user.email == cleaned_data.get("email") and existing_profile.user.is_active:
                # stop users who already exist registering another account unless it has been made inactive
                return proposed_username # return this username and cause the form to error out on duplicate

        # this person is probably a different person with the same name as someone else
        #  or someone who cannot keep track of their email addresses, create a new incremented username anyway
        proposed_username = "%s%d" % (proposed_username, potentially_existing_profiles.count()+1)
    return proposed_username


@sensitive_post_parameters('password1', 'password2')
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
def form_credit(request, credit_code=None):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp
    if not hasattr(request.user, "profile"):
        return HttpResponseBadRequest() # bye

    credit = None
    init = None

    if credit_code:
        if request.method == "POST":
            credit = models.InstituteCredit.objects.filter(credit_code=credit_code).first()
        else:
            credit = get_object_or_404(models.InstituteCredit, credit_code=credit_code)

    if credit:
        if credit.institute != request.user.profile.institute:
            return HttpResponseBadRequest() # bye
        init = model_to_dict(credit)

    if request.method == "POST":
        post = request.POST.copy()
        if credit:
            post["credit_code"] = credit.credit_code
        form = forms.CreditForm(post, initial=init)
        if form.is_valid():
            proposed_cc = form.cleaned_data["credit_code"]
            if not credit:
                proposed_cc = "%s:%s" % (request.user.profile.institute.code, form.cleaned_data["credit_code"])
            credit, created = models.InstituteCredit.objects.get_or_create(
                    institute=request.user.profile.institute,
                    credit_code=proposed_cc.upper(),
            )
            if not created:
                if credit.institute != request.user.profile.institute:
                    return HttpResponseBadRequest() # bye

                if form.cleaned_data.get("delete"):
                    credit.delete()
                    return render(request, 'accounts/institute_success.html')

            credit.lab_name = form.cleaned_data["lab_name"]
            credit.lab_addr = form.cleaned_data["lab_addr"]
            credit.lab_list = form.cleaned_data["lab_list"]
            if credit.lab_list:
                credit.lab_list = credit.lab_list.replace('\t', ' ').replace('\r', '').replace('\n', ',').replace(",,", ',').replace(' ,', ',') # sigh
            credit.save()
            return render(request, 'accounts/institute_success.html')
        else:
            if credit:
                form.fields['credit_code'].disabled = True
                form.fields['credit_code'].required = False
    else:
        form = forms.CreditForm(initial=init)
        if credit:
            form.fields['credit_code'].disabled = True
            form.fields['credit_code'].required = False
    return render(request, 'forms/credit.html', {'form': form, 'credit_code': credit_code})


@login_required
def form_institute(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

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
            org.ena_assembly_opted = form.cleaned_data.get("ena_assembly_opted")
            org.credit_code_only = form.cleaned_data.get("credit_code_only")
            if org.gisaid_list:
                org.gisaid_list = org.gisaid_list.replace('\t', ' ').replace('\r', '').replace('\n', ',').replace(",,", ',').replace(' ,', ',') # sigh
            org.save()
            return render(request, 'accounts/institute_success.html')
    else:
        form = forms.InstituteForm(initial=init)
    return render(request, 'forms/institute.html', {'form': form, 'institute': org})


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
                        '1' if user.profile.is_revoked else '0',
                        user.username,
                        user.first_name,
                        user.last_name,
                        user.email,
                        user.profile.institute.code
                    ]))
            return HttpResponse("\n".join(keys), content_type="text/plain")
    return HttpResponseBadRequest() # bye

@login_required
def list_dataviews(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    generated = models.MajoraDataviewUserPermission.objects.filter(profile=request.user.profile)
    available = []

    return render(request, 'dataviews.html', {
        'user': request.user,
        'available': available,
        'generated': generated,
    })

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
def agreements(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    signed = models.ProfileAgreement.objects.filter(profile=request.user.profile, is_terminated=False)
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
        #TODO Do we need to manually check the CSRF? I think this might be done by django middleware automatically
        #TODO Tatl call here?

        form_action = request.POST.get("action")
        if not form_action:
            return HttpResponseBadRequest() # bye

        if form_action == "sign":
            try:
                # Check not already signed
                signature = models.ProfileAgreement.objects.get(agreement__slug=slug, profile=request.user.profile, is_terminated=False)
                agreement = signature.agreement
                signed = True
            except:
                try:
                    agreement = models.ProfileAgreementDefinition.objects.get(slug=slug)
                    signed = False
                except:
                    return HttpResponseBadRequest() # bye

                signature = models.ProfileAgreement(
                    agreement = agreement,
                    profile = request.user.profile,
                    signature_timestamp = timezone.now(),
                )
                signed = True
                signature.save()
        elif form_action == "terminate":
            try:
                # Check already signed
                signature = models.ProfileAgreement.objects.get(agreement__slug=slug, profile=request.user.profile, is_terminated=False)
                agreement = signature.agreement
                signed = True

                if not agreement.is_terminable:
                    # Nice try pal
                    return HttpResponseBadRequest() # bye

                signature.is_terminated = True
                signature.terminated_timestamp = timezone.now()
                signature.terminated_reason = "TERMINATED BY USER"
                signature.save()
                signed = False

            except:
                return HttpResponseBadRequest() # bye

        else:
            return HttpResponseBadRequest() # bye

    else:
        # VIEWING AGREEMENT
        try:
            signature = models.ProfileAgreement.objects.get(agreement__slug=slug, profile=request.user.profile, is_terminated=False)
            agreement = signature.agreement
            signed = True
        except:
            try:
                agreement = models.ProfileAgreementDefinition.objects.get(slug=slug)
                signed = False
            except:
                return HttpResponseBadRequest() # bye

    old_sigs = models.ProfileAgreement.objects.filter(agreement__slug=slug, profile=request.user.profile, is_terminated=True)
    return render(request, 'view_agreement.html', {
        'user': request.user,
        'previous_signatures': old_sigs,
        'agreement': agreement,
        'signature': signature,
        'signed': signed,
    })
