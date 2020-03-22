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
from . import fixed_data
from . import form_handlers

import json


@csrf_exempt
def wrap_api_v2(request, f):

    api_o = {
        "errors": 0,
        "warnings": 0,
        "messages": [],

        "new": [],
        "updated": [],
        "ignored": [],
    }

    # Bounce non-POST
    if request.method != "POST":
        return HttpResponseBadRequest()

    # Bounce badly formatted requests
    json_data = json.loads(request.body)
    if not json_data.get('token', None) or not json_data.get('username', None):
        return HttpResponseBadRequest()

    # Bounce unauthorised requests
    profile = None
    try:
        profile = models.Profile.objects.get(api_key=json_data["token"], user__username=json_data["username"])
    except:
        return HttpResponseBadRequest()

    # Call the wrapped function
    f(request, api_o, json_data, user=profile.user)

    api_o["success"] = api_o["errors"] == 0
    return HttpResponse(json.dumps(api_o), content_type="application/json")


def add_biosample(request):
    def f(request, api_o, json_data, user=None):
        biosamples = json_data.get("biosamples", {})
        if not biosamples:
            api_o["messages"].append("'biosamples' key missing or empty")
            api_o["errors"] += 1

        for biosample in biosamples:
            try:
                sample_id = biosample.get("sample_id")
                initial = fixed_data.fill_fixed_data("api.biosample.add", user)
                form = forms.TestSampleForm(biosample, initial=initial)
                if form.is_valid():
                    form.cleaned_data.update(initial)
                    sample = form_handlers.handle_testsample(form, user)
                    if sample:
                        api_o["new"].append(str(sample.id))
                    else:
                        if sample_id:
                            api_o["ignored"].append(sample_id)
                        api_o["errors"] += 1
                else:
                    api_o["errors"] += 1
                    api_o["ignored"].append(sample_id)
                    api_o["messages"].append(form.errors.get_json_data())
            except Exception as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))

    return wrap_api_v2(request, f)

def add_digitalresource(request):
    pass
