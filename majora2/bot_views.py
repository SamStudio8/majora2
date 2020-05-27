from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.auth.models import User, Permission

from django.utils import timezone

import json
from . import signals
from . import models

#TODO should probably have a common entry system like the api_view

def bot_approve_registration(request):
    if request.method == "POST":
        try:
            perm = Permission.objects.get(codename='can_approve_profiles_via_bot')
            profile = models.Profile.objects.get(user__user_permissions=perm, slack_id=request.POST.get('user_id'))
        except Exception as e:
            return HttpResponse(json.dumps({
                "response_type": "ephemeral",
                "text": "I'm sorry %s. I'm afraid I can't do that." % request.POST.get('user_name', "User"),
            }), content_type="application/json")

        user = request.POST.get('text', None)
        if not user:
            return HttpResponse(json.dumps({
                "response_type": "ephemeral",
                "text": "You didn't specify a username to approve.",
            }), content_type="application/json")

        user = User.objects.get(username=user)
        if not user:
            return HttpResponse(json.dumps({
                "response_type": "ephemeral",
                "text": "Invalid username.",
            }), content_type="application/json")

        if profile and not user.is_active:
            user.is_active = True
            user.save()
            user.profile.is_site_approved = True # force local site approval if its approved by sysadm
            user.profile.save()

            from tatl.models import TatlPermFlex
            treq = TatlPermFlex(
                user = profile.user,
                substitute_user = None,
                used_permission = perm.codename,
                timestamp = timezone.now(),
                content_object = user.profile,
            )
            treq.save()
            signals.activated_registration.send(sender=request, username=user.username, email=user.email)

            return HttpResponse(json.dumps({
                "response_type": "in_channel",
                "text": "User %s is now active and able to authenticate." % user.username,
            }), content_type="application/json")
    else:
        return HttpResponseBadRequest()
