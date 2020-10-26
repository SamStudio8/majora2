from django.shortcuts import render
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.contrib.auth.decorators import login_required

from . import models as dmodels
from majora2 import models
from tatl.util import django_2fa_mixin_hack

@login_required
def list_all_profiles(request):
    otp = django_2fa_mixin_hack(request)
    if otp:
        return otp

    if not hasattr(request.user, "profile"):
        return HttpResponseBadRequest() # bye

    if not request.user.has_perm("majora2.change_profile"):
        return HttpResponseForbidden() # bye

    # Render the list regardless of what the form did
    active_site_profiles = models.Profile.objects.filter(is_site_approved=True)
    inactive_site_profiles = models.Profile.objects.filter(is_site_approved=False)
    return render(request, 'site_profiles.html', {
        'user': request.user,
        'org': request.user.profile.institute,
        'active_profiles': active_site_profiles,
        'inactive_profiles': inactive_site_profiles,
    })

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
