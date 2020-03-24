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
                sample_id = biosample.get("central_sample_id")
                initial = fixed_data.fill_fixed_data("api.artifact.biosample.add", user)
                form = forms.TestSampleForm(biosample, initial=initial)
                if form.is_valid():
                    form.cleaned_data.update(initial)
                    sample, sample_created = form_handlers.handle_testsample(form, user=user, api_o=api_o)
                    if not sample:
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

def add_sequencing(request):
    def f(request, api_o, json_data, user=None):
        library_name = json_data.get("library_name")
        if not library_name:
            api_o["messages"].append("'library_name' key missing or empty")
            api_o["errors"] += 1
            return
        biosamples = json_data.get("biosamples", {})
        if not biosamples:
            api_o["messages"].append("'biosamples' key missing or empty")
            api_o["errors"] += 1
            return

        try:
            initial = fixed_data.fill_fixed_data("api.artifact.library.add", user)
            form = forms.TestLibraryForm(json_data, initial=initial)
            if form.is_valid():
                form.cleaned_data.update(initial)
                library, library_created = form_handlers.handle_testlibrary(form, user=user, api_o=api_o)
                if not library:
                    api_o["ignored"].append(library_name)
                    api_o["errors"] += 1
            else:
                api_o["errors"] += 1
                api_o["ignored"].append(library_name)
                api_o["messages"].append(form.errors.get_json_data())
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

        # Add samples to library
        for biosample in biosamples:
            try:
                sample_id = biosample.get("central_sample_id")
                initial = fixed_data.fill_fixed_data("api.processrecord.library.add", user)
                biosample["library_name"] = library_name
                form = forms.TestLibraryBiosampleForm(biosample, initial=initial)
                if form.is_valid():
                    form.cleaned_data.update(initial)
                    record, record_created = form_handlers.handle_testlibraryrecord(form, user=user, api_o=api_o)
                    if not record:
                        api_o["ignored"].append(sample_id)
                        api_o["errors"] += 1
                else:
                    api_o["errors"] += 1
                    api_o["ignored"].append(initial)
                    api_o["messages"].append(form.errors.get_json_data())
            except Exception as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))

        try:
            json_data = forms.TestSequencingForm.modify_preform(json_data)
            initial = fixed_data.fill_fixed_data("api.process.sequencing.add", user)
            form = forms.TestSequencingForm(json_data, initial=initial)
            if form.is_valid():
                form.cleaned_data.update(initial)
                sequencing, sequencing_created = form_handlers.handle_testsequencing(form, user=user, api_o=api_o)
            else:
                api_o["errors"] += 1
                api_o["messages"].append(form.errors.get_json_data())
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))


    return wrap_api_v2(request, f)

def add_digitalresource(request):
    def f(request, api_o, json_data, user=None):
        pass
    return wrap_api_v2(request, f)
