from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.contrib.auth.decorators import login_required
from django.utils import timezone


from django.contrib.auth.models import User
from django.conf import settings

from . import models
from . import util
from . import forms
from . import signals
from . import fixed_data
from . import form_handlers

import json

MINIMUM_CLIENT_VERSION = "0.1.2"

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

    bad = False
    # Bounce out of data clients
    if json_data.get("client_name") == "ocarina":
        try:
            server_version = tuple(map(int, (MINIMUM_CLIENT_VERSION.split("."))))
            client_version = tuple(map(int, (json_data["client_version"].split("."))))
            if client_version < server_version:
                api_o["messages"].append("Update your 'ocarina' client to version v%s" % MINIMUM_CLIENT_VERSION)
                api_o["errors"] += 1
                bad = True
        except:
            api_o["messages"].append("It appears you are using 'ocarina', but your version number doesn't make sense... This shouldn't happen...")
            api_o["errors"] += 1
            bad = True

    # Call the wrapped function
    if not bad:
        f(request, api_o, json_data, user=profile.user)

    api_o["success"] = api_o["errors"] == 0
    return HttpResponse(json.dumps(api_o), content_type="application/json")


def handle_metadata(metadata, tag_type, tag_to, user, api_o):
    ts = timezone.now()
    for tag_key in metadata:
        for key in metadata[tag_key]:
            t_data = {
                tag_type: tag_to,
                "tag": tag_key,
                "timestamp": ts,
            }
            t_data["name"] = key
            t_data["value"] = metadata[tag_key][key]
            form = forms.TestMetadataForm(t_data)
            if form.is_valid():
                majora_meta, created = form_handlers.handle_testmetadata(form, user=user, api_o=api_o)
                if not created:
                    #TODO catch
                    pass
                if not majora_meta:
                    api_o["warnings"] += 1
                    api_o["ignored"].append("metadata__%s__%s" % (t_data.get("tag"), t_data.get("name")))
            else:
                api_o["errors"] += 1
                api_o["ignored"].append("metadata__%s__%s" % (t_data.get("tag"), t_data.get("name")))
                api_o["messages"].append(form.errors.get_json_data())

def get_biosample(request):
    def f(request, api_o, json_data, user=None):
        sample_id = json_data.get("central_sample_id")
        if not sample_id:
            api_o["messages"].append("'central_sample_id' key missing or empty")
            api_o["errors"] += 1
            return

        try:
            artifact = models.MajoraArtifact.objects.filter(dice_name=sample_id).first()

            api_o["get"] = {
                sample_id: artifact.as_struct()
            }
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

    return wrap_api_v2(request, f)


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
                        handle_metadata(biosample.get("metadata", {}), 'artifact', sample.dice_name, user, api_o)
                else:
                    api_o["errors"] += 1
                    api_o["ignored"].append(sample_id)
                    api_o["messages"].append(form.errors.get_json_data())
            except Exception as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))

    return wrap_api_v2(request, f)

def add_library(request):
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

        library = None
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

            handle_metadata(json_data.get("metadata", {}), 'artifact', library_name, user, api_o)
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

        if not library:
            return

        # Check samples exist, and create them if the right flag has been set
        sample_missing = False
        sample_forced = False
        for biosample in biosamples:
            sample_id = biosample.get("central_sample_id")
            if json_data.get("force_biosamples"):
                # Make dummy sample
                biosample, created = models.BiosampleArtifact.objects.get_or_create(
                        central_sample_id=sample_id,
                        dice_name=sample_id
                )
                if created:
                    api_o["new"].append(form_handlers._format_tuple(biosample))
                    api_o["warnings"] += 1
                    sample_forced = True
            else:
                if models.BiosampleArtifact.objects.filter(central_sample_id=sample_id).count() != 1:
                    api_o["ignored"].append(sample_id)
                    api_o["errors"] += 1
                    sample_missing = True

        if sample_missing:
            api_o["messages"].append("At least one Biosample in your Library was not registered. No samples have been added to this Library. Register the missing samples, or remove them from your request and try again.")
            return
        if sample_forced:
            api_o["messages"].append("You forced the creation of at least one Biosample. This sample will be ignored by CLIMB pipelines and reports until its metadata has been registered.")

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

    return wrap_api_v2(request, f)

def add_sequencing(request):
    def f(request, api_o, json_data, user=None):
        library_name = json_data.get("library_name")
        if not library_name:
            api_o["messages"].append("'library_name' key missing or empty")
            api_o["errors"] += 1
            return
        runs = json_data.get("runs", {})
        if not runs:
            api_o["messages"].append("'runs' key missing or empty")
            api_o["errors"] += 1
            return

        # Add sequencing runs to library
        for run in runs:
            try:
                json_data = forms.TestSequencingForm.modify_preform(json_data)
                initial = fixed_data.fill_fixed_data("api.process.sequencing.add", user)
                run["library_name"] = library_name
                form = forms.TestSequencingForm(run, initial=initial)
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

        node_name = json_data.get("node_name")
        if not node_name and user and hasattr(user, "profile"):
            node_name = user.profile.institute.code
            # Just add the node if it does not exist?
            node, created = models.DigitalResourceNode.objects.get_or_create(
                unique_name = node_name,
                dice_name = node_name,
                meta_name = node_name,
                node_name = node_name,
            )
            json_data["node_name"] = node.dice_name

        # Try to add file
        try:
            initial = fixed_data.fill_fixed_data("api.artifact.digitalresource.add", user)
            form = forms.TestFileForm(json_data, initial=initial)
            if form.is_valid():
                form.cleaned_data.update(initial)
                mfile, created = form_handlers.handle_testdigitalresource(form, user=user, api_o=api_o)
                if not mfile:
                    api_o["ignored"].append(json_data.get("path"))
                    api_o["errors"] += 1
                elif mfile:
                    handle_metadata(json_data.get("metadata", {}), 'artifact', mfile.id, user, api_o)
            else:
                api_o["errors"] += 1
                api_o["messages"].append(form.errors.get_json_data())
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

    return wrap_api_v2(request, f)


def add_tag(request):
    def f(request, api_o, json_data, user=None):

        if json_data.get("artifact"):
            handle_metadata(json_data.get("metadata", {}), 'artifact', json_data.get("artifact"), user, api_o)
        elif json_data.get("group"):
            handle_metadata(json_data.get("metadata", {}), 'group', json_data.get("group"), user, api_o)
        elif json_data.get("process"):
            handle_metadata(json_data.get("metadata", {}), 'process', json_data.get("process"), user, api_o)

    return wrap_api_v2(request, f)
