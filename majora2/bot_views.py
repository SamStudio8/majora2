from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.auth.models import User

import json

def bot_approve_registration(request):
    if request.method == "POST":
        if request.POST.get('user_id', None) not in settings.SLACK_USERS:
            return HttpResponse(json.dumps({
                "response_type": "ephemeral",
                "text": "I'm sorry %. I'm afraid I can't do that." % request.POST.get('user_name', "User"),
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
        else:
            user.is_active = True
            user.save()
            return HttpResponse(json.dumps({
                "response_type": "in_channel",
                "text": "User %s is now active and able to authenticate." % user.username,
            }), content_type="application/json")
    else:
        return HttpResponseBadRequest()
