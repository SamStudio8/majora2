from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views import View


from django.contrib.auth.models import User
from django.conf import settings

from . import models
from . import util
from . import forms
from . import signals
from . import fixed_data
from . import form_handlers
from .form_handlers import _format_tuple


import json
import uuid
import datetime

from tatl.models import TatlVerb

MINIMUM_CLIENT_VERSION = "0.37.0"

@csrf_exempt
def wrap_api_v2(request, f, permission=None, oauth_permission=None, partial=False, stream=False, get=False, oauth_only=False):
    from tatl.models import TatlRequest, TatlPermFlex

    start_ts = timezone.now()
    api_o = {
        "errors": 0,
        "warnings": 0,
        "messages": [],

        "tasks": [],

        "new": [],
        "updated": [],
        "ignored": [],
    }
    api_o["request"] = str(request.treq.response_uuid)

    if not get:
        # Bounce non-POST for post (not get) interfaces
        if request.method != "POST":
            return HttpResponseBadRequest()

        try:
            json_data = json.loads(request.body)
        except:
            return HttpResponseBadRequest()

        # Bounce badly formatted requests
        if not json_data.get('token', None) or not json_data.get('username', None):
            return HttpResponseBadRequest()

    else:
        # Bounce non-GET if get flag is set
        if request.method != "GET":
            return HttpResponseBadRequest()

        # Set json_data to GET params, skipping check for token/username
        json_data = request.GET

    profile = None


    oauth = False
    if hasattr(request, "tatl_oauth") and request.tatl_oauth:
        oauth = True

        # borrowed from the oauth2_provider backend
        from oauth2_provider.oauth2_backends import get_oauthlib_core
        OAuthLibCore = get_oauthlib_core()

        # now check the request for the right scopes
        valid, r = OAuthLibCore.verify_request(request, scopes=oauth_permission.split(" ") if oauth_permission else [])
        if valid:
            profile = request.user.profile
            user = request.user
        else:
            #TODO This should return 401 probably
            api_o["messages"].append("Your token is valid but does not have all of the scopes to perform this action. Required scopes: %s" % oauth_permission)
            api_o["errors"] += 1
            bad = True
            return HttpResponse(json.dumps(api_o), content_type="application/json")
    elif oauth_only:
        return HttpResponseBadRequest()
    else:
        if get:
            # GET API endpoints are OAuth only
            return HttpResponseBadRequest()

        try:
            # Check new key validity
            key = models.ProfileAPIKey.objects.get(key=json_data["token"], profile__user__username=json_data["username"], was_revoked=False, validity_start__lt=timezone.now(), validity_end__gt=timezone.now())
            profile = key.profile
        except:
            return HttpResponseBadRequest()
            #api_o["messages"].append("That key does not exist, has expired or was revoked")
            #api_o["errors"] += 1
            #bad = True
        user = profile.user

        if permission:
            # Check permission has been granted to user
            if not user.has_perm(permission):
                return HttpResponseBadRequest()

            # Check permission has been granted to key
            if not key.key_definition.permission:
                return HttpResponseBadRequest()
            if key.key_definition.permission.codename != permission.split('.')[1]:
                return HttpResponseBadRequest()

    # If in doubt
    if not profile or not user.is_active or user.profile.is_revoked:
        return HttpResponseBadRequest()

    request.treq.is_api = True
    request.treq.user = user
    request.treq.save()

    if permission and not oauth:
        tflex = TatlPermFlex(
            user = user,
            substitute_user = None,
            used_permission = permission,
            timestamp = timezone.now(),
            request=request.treq,
            content_object = request.treq, #TODO just use the request for now
        )
        tflex.save()

    # Bounce non-admin escalations to other users
    if json_data.get("sudo_as"):
        if user.is_staff:
            try:
                user = models.Profile.objects.get(user__username=json_data["sudo_as"]).user
                request.treq.substitute_user = user
                request.treq.save()

                if permission:
                    tflex.substitute_user = user
                    tflex.save()
            except:
                return HttpResponseBadRequest()
        else:
            return HttpResponseBadRequest()


    bad = False
    # Bounce out of date clients
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
    if not bad and profile:
        possible_fstream = f(request, api_o, json_data, user=user, partial=partial)

    api_o["success"] = api_o["errors"] == 0

    end_ts = timezone.now()
    request.treq.save()

    if stream and possible_fstream:
        return possible_fstream
    else:
        return HttpResponse(json.dumps(api_o), content_type="application/json")


def handle_metadata(metadata, tag_type, tag_to, user, api_o):

    changed_fields = []
    #nulled_fields = []

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
                majora_meta, created, updated = form_handlers.handle_testmetadata(form, user=user, api_o=api_o)
                if not created:
                    #TODO catch
                    pass
                if not majora_meta:
                    api_o["warnings"] += 1
                    api_o["ignored"].append("metadata__%s__%s" % (t_data.get("tag"), t_data.get("name")))

                if updated:
                    changed_fields.append("metadata:%s.%s" % (t_data.get("tag"), t_data.get("name")))

                #if t_data.get("value") is None:
                #    # Nuke the record if it has been None'd
                #    if majora_meta.delete()[0] == 1:
                #        api_o["messages"].append("Deleted: metadata__%s__%s" % (t_data.get("tag"), t_data.get("name")))
            else:
                api_o["errors"] += 1
                api_o["ignored"].append("metadata__%s__%s" % (t_data.get("tag"), t_data.get("name")))
                api_o["messages"].append(form.errors.get_json_data())
    return changed_fields

#TODO Abstract this away info form handlers per-metric, use modelforms properly
def handle_metrics(metrics, tag_type, tag_to, user, api_o):
    updated_metrics = []

    ts = timezone.now()
    for metric in metrics:
        metrics[metric]["artifact"] = tag_to.id
        metrics[metric]["namespace"] = metric

        is_model = True
        if metric == "sequence":
            m = models.TemporaryMajoraArtifactMetric_Sequence.objects.filter(artifact=tag_to).first()
            form = forms.M2Metric_SequenceForm(metrics[metric], instance=m)
        elif metric == "mapping":
            m = models.TemporaryMajoraArtifactMetric_Mapping.objects.filter(artifact=tag_to).first()
            form = forms.M2Metric_MappingForm(metrics[metric], instance=m)
        elif metric == "tile-mapping":
            m = models.TemporaryMajoraArtifactMetric_Mapping_Tiles.objects.filter(artifact=tag_to).first()
            form = forms.M2Metric_MappingTileForm(metrics[metric], instance=m)
        elif metric == "ct":
            m = models.TemporaryMajoraArtifactMetric_ThresholdCycle.objects.filter(artifact=tag_to).first()
            metrics[metric]["num_tests"] = 0
            metrics[metric]["min_ct"] = 0
            metrics[metric]["max_ct"] = 0
            form = forms.M2Metric_ThresholdCycleForm(metrics[metric], instance=m)

            # Catch null values gently on uploader
            any_ct = False
            for metric_rec_name in metrics[metric].get("records", {}):
                metric_rec = metrics[metric]["records"][metric_rec_name]
                if metric_rec.get("ct_value"):
                    any_ct = True
            if not any_ct:
                api_o["ignored"].append("%s" % metric)
                api_o["messages"].append("'%s' records look empty" % metric)
                api_o["warnings"] += 1
                continue
        else:
            api_o["ignored"].append(metric)
            api_o["messages"].append("'%s' does not describe a valid metric" % metric)
            api_o["warnings"] += 1
            continue

        if form.is_valid():
            try:
                metric_ob = form.save()
                if metric_ob:
                    api_o["updated"].append(_format_tuple(tag_to))

                    # Handle optional records
                    first_valid = True
                    for metric_rec_name in metrics[metric].get("records", {}):
                        metric_rec = metrics[metric]["records"][metric_rec_name]
                        if metric == "ct":
                            metric_rec["artifact_metric"] = metric_ob
                            form = forms.M2MetricRecord_ThresholdCycleForm(metric_rec)
                            # Catch null values gently on uploader
                            if not metric_rec.get("ct_value"):
                                api_o["ignored"].append("%s:%s" % (metric, metric_rec_name))
                                api_o["warnings"] += 1
                                continue
                            if form.is_valid():
                                if first_valid:
                                    # Destroy existing records
                                    dc = metric_ob.metric_records.all().delete()[0] # bye
                                    if dc > 0:
                                        api_o["messages"].append("%d existing Ct value records deleted and replaced with new values" % int(dc/2))
                                        updated_metrics = [metric]
                                    first_valid = False
                                try:
                                    artifact_metric = form.cleaned_data["artifact_metric"]
                                    rec_obj, rec_obj_created = models.TemporaryMajoraArtifactMetricRecord_ThresholdCycle.objects.get_or_create(
                                            artifact_metric = artifact_metric,
                                            test_platform = form.cleaned_data.get("test_platform"),
                                            test_target = form.cleaned_data.get("test_target"),
                                            test_kit = form.cleaned_data.get("test_kit"),
                                    )
                                    if rec_obj:
                                        rec_obj.ct_value = form.cleaned_data["ct_value"]
                                        rec_obj.save()
                                        artifact_metric.num_tests = len(artifact_metric.metric_records.all())
                                        ct_min = None
                                        ct_max = None
                                        for record in artifact_metric.metric_records.all():
                                            ct = record.ct_value
                                            if not ct_min:
                                                ct_min = ct
                                            elif ct < ct_min:
                                                ct_min = ct

                                            if not ct_max:
                                                ct_max = ct
                                            elif ct > ct_max:
                                                ct_max = ct

                                        artifact_metric.min_ct = ct_min
                                        artifact_metric.max_ct = ct_max
                                        artifact_metric.save()

                                    if not rec_obj:
                                        api_o["ignored"].append("%s:%s" % (metric, metric_rec_name))
                                        api_o["errors"] += 1
                                except Exception as e:
                                    api_o["errors"] += 1
                                    api_o["messages"].append(str(e))
                            else:
                                api_o["errors"] += 1
                                api_o["ignored"].append("%s:%s" % (metric, metric_rec_name))
                                api_o["messages"].append(form.errors.get_json_data())
                        # End Metric Records
                else:
                    api_o["ignored"].append(metric)
                    api_o["errors"] += 1
            except Exception as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))
        else:
            api_o["errors"] += 1
            api_o["ignored"].append(metric)
            api_o["messages"].append(form.errors.get_json_data())
    return updated_metrics




def biosample_query_validity(request):
    def f(request, api_o, json_data, user=None, partial=False):
        biosamples = json_data.get("biosamples", {})
        if not biosamples:
            api_o["messages"].append("'biosamples' key missing or empty")
            api_o["errors"] += 1

        api_o["result"] = {}
        for biosample in biosamples:

            exists = False
            has_metadata = False
            has_sender = False

            bs = models.BiosampleArtifact.objects.filter(central_sample_id=biosample).first()

            if bs:
                exists = True
                if bs.sender_sample_id and len(bs.sender_sample_id) > 0:
                    has_sender = True

                if bs.created:
                    if bs.created.collection_location_country and len(bs.created.collection_location_country) > 0:
                        has_metadata = True
            api_o["result"][biosample] = {
                "central_sample_id": bs.central_sample_id if bs else None,
                "exists": exists,
                "has_sender_id": has_sender,
                "has_metadata": has_metadata
            }

    return wrap_api_v2(request, f)

def get_biosample(request):
    def f(request, api_o, json_data, user=None, partial=False):
        sample_id = json_data.get("central_sample_id")
        if not sample_id:
            api_o["messages"].append("'central_sample_id' key missing or empty")
            api_o["errors"] += 1
            return

        try:
            artifact = models.MajoraArtifact.objects.filter(dice_name=sample_id).first()
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append("No such artifact.")
            return

        try:
            api_o["get"] = {
                sample_id: artifact.as_struct()
            }
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

    return wrap_api_v2(request, f)

def get_sequencing(request):
    def f(request, api_o, json_data, user=None, partial=False):
        run_names = json_data.get("run_name")
        if not run_names:
            api_o["messages"].append("'run_name' key missing or empty")
            api_o["errors"] += 1
            return

        if len(run_names) == 1 and run_names[0] == "*":
            if user.is_staff:
                from . import tasks
                celery_task = tasks.task_get_sequencing.delay(None, api_o, json_data, user=user.pk if user else None, response_uuid=api_o["request"])
                if celery_task:
                    api_o["tasks"].append(celery_task.id)
                    api_o["messages"].append("Call api.majora.task.get with the appropriate task ID later...")
                else:
                    api_o["errors"] += 1
                    api_o["messages"].append("Could not add requested task to Celery...")
            else:
                return HttpResponseBadRequest()

        runs = {}
        for run_name in run_names:
            try:
                process = models.DNASequencingProcess.objects.get(run_name=run_name)
            except Exception as e:
                api_o["warnings"] += 1
                api_o["ignored"].append(run_name)
                continue

            try:
                runs[process.run_name] = process.as_struct()
            except Exception as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))
                continue
        api_o["get"] = runs

    return wrap_api_v2(request, f)


def get_sequencing2(request):
    def f(request, api_o, json_data, user=None, partial=False):
        run_names = json_data.get("run_name")
        if not run_names:
            api_o["messages"].append("'run_name' key missing or empty")
            api_o["errors"] += 1
            return

        if len(run_names) == 1 and run_names[0] == "*":
            if user.is_staff:
                from . import tasks
                celery_task = tasks.task_get_sequencing_faster.delay(None, api_o, json_data, user=user.pk if user else None, response_uuid=api_o["request"])
                if celery_task:
                    api_o["tasks"].append(celery_task.id)
                    api_o["messages"].append("Call api.majora.task.get with the appropriate task ID later...")
                else:
                    api_o["errors"] += 1
                    api_o["messages"].append("Could not add requested task to Celery...")
            else:
                return HttpResponseBadRequest()

        runs = {}
        for run_name in run_names:
            try:
                process = models.DNASequencingProcess.objects.get(run_name=run_name)
            except Exception as e:
                api_o["warnings"] += 1
                api_o["ignored"].append(run_name)
                continue

            try:
                runs[process.run_name] = process.as_struct()
            except Exception as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))
                continue
        api_o["get"] = runs

    return wrap_api_v2(request, f)


def add_qc(request):
    def f(request, api_o, json_data, user=None, partial=False):
        pag_name = json_data.get("publish_group")
        test_name = json_data.get("test_name")
        test_version = json_data.get("test_version")

        if (not pag_name) or (not test_name) or (not test_version):
            api_o["messages"].append("'pag_name', 'test' or 'version' key missing or empty")
            api_o["errors"] += 1
            return
        if len(pag_name)==0 or len(test_name)==0 or len(str(test_version))==0:
            api_o["messages"].append("'pag_name', 'test' or 'version' key missing or empty")
            api_o["errors"] += 1
            return

        pag = models.PublishedArtifactGroup.objects.filter(is_latest=True, published_name=pag_name).first() # There can be only one
        if not pag:
            api_o["messages"].append("Invalid 'pag_name'")
            api_o["ignored"].append(pag_name)
            api_o["errors"] += 1
            return

        t_group = models.PAGQualityTestEquivalenceGroup.objects.filter(slug=test_name).first()
        if not t_group:
            api_o["messages"].append("Invalid 'test_name'")
            api_o["ignored"].append(pag_name)
            api_o["errors"] += 1
            return

        # Gather metrics from PAG
        metrics = {}
        for artifact in pag.tagged_artifacts.all():
            # For this project we don't need to worry about duplicates
            # but this is an outstanding problem... TODO
            for metric in artifact.metrics.all():
                if metric.namespace:
                    if metric.namespace not in metrics:
                        metrics[metric.namespace] = metric.as_struct()
                    else:
                        api_o["messages"].append("Cannot automatically QC a PAG with multiple objects containing the same metric type...")
                        api_o["errors"] += 1
                        return

        # Gather metadata from PAG
        metadata = {}
        for artifact in pag.tagged_artifacts.all():
            curr_meta = artifact.get_metadata_as_struct()
            for namespace in curr_meta:
                if namespace not in metadata:
                    metadata[namespace] = {}
                for meta_name in curr_meta[namespace]:
                    if meta_name not in metadata[namespace]:
                        metadata[namespace][meta_name] = curr_meta[namespace][meta_name]
                    elif metadata[namespace][meta_name] != curr_meta[namespace][meta_name]:
                        api_o["messages"].append("Cannot automatically QC a PAG with multiple objects containing the same metadata fields with different values...")
                        api_o["errors"] += 1
                        return
                    else:
                        pass

        n_fails = 0
        test_data = {}
        all_skipped = True # flag to determine at least one QC test was run
        for test in t_group.tests.all():
            # Get the latest test version
            tv = test.versions.order_by('-version_number').first()
            test_data[tv] = {
                "results": {},
                "decisions": {},
                "is_pass": None,
                "is_skip": None,
            }

            is_match = False
            is_skip = False
            # Determine if we need to skip this test
            for tfilter in test.filters.all():
                meta = metadata.get(tfilter.metadata_namespace, {}).get(tfilter.metadata_name, None)
                if meta:
                    meta = str(meta).upper()
                    if tfilter.op == "EQ":
                        is_match = meta == tfilter.filter_on_str
                    elif tfilter.op == "NEQ":
                        is_match = meta != tfilter.filter_on_str
                    else:
                        pass
                    is_skip = not is_match
                else:
                    if tfilter.force_field:
                        api_o["messages"].append("Cannot automatically QC a PAG that is missing required metadata (%s.%s)" % (tfilter.metadata_namespace, tfilter.metadata_name))
                        api_o["errors"] += 1
                        return

            if is_skip:
                test_data[tv]["is_skip"] = True
                test_data[tv]["is_pass"] = False
                continue # to next test
            else:
                all_skipped = False
                test_data[tv]["is_skip"] = False


            for rule in tv.rules.all():
                curr_res = {
                    "rule": rule,
                    "test_metric_str": None,
                    "is_pass": None,
                    "is_warn": None,
                    "is_fail": None,
                }
                # Determine if the test can be performed
                if rule.metric_namespace not in metrics:
                    api_o["messages"].append("Namespace %s not found in metrics" % rule.metric_namespace)
                    api_o["ignored"].append(rule.metric_namespace)
                    api_o["errors"] += 1
                    continue
                if rule.metric_name not in metrics[rule.metric_namespace] or metrics[rule.metric_namespace][rule.metric_name] is None:
                    api_o["messages"].append("Metric %s.%s not found in metrics" % (rule.metric_namespace, rule.metric_name))
                    api_o["ignored"].append(rule.metric_name)
                    api_o["errors"] += 1
                    continue
                curr_metric = metrics[rule.metric_namespace][rule.metric_name]
                curr_res["test_metric_str"] = str(curr_metric)

                if not rule.warn_min and not rule.warn_max:
                    curr_res["is_warn"] = False
                else:
                    # Check warnings
                    if rule.warn_min:
                        if curr_metric < rule.warn_min:
                            curr_res["is_warn"] = True
                        else:
                            curr_res["is_warn"] = False
                    if not curr_res["is_warn"] and rule.warn_max:
                        if curr_metric >= rule.warn_max:
                            curr_res["is_warn"] = True
                        else:
                            curr_res["is_warn"] = False

                if not rule.fail_min and not rule.fail_max:
                    curr_res["is_fail"] = False
                else:
                    # Check failures
                    if rule.fail_min:
                        if curr_metric < rule.fail_min:
                            curr_res["is_fail"] = True
                        else:
                            curr_res["is_fail"] = False

                    if not curr_res["is_fail"] and rule.fail_max:
                        if curr_metric >= rule.fail_max:
                            curr_res["is_fail"] = True
                        else:
                            curr_res["is_fail"] = False

                curr_res["is_pass"] = not curr_res["is_fail"]
                test_data[tv]["results"][rule] = curr_res

            #TODO What if the same rule is checked many times? (It should not be anyway but...)
            if len(test_data[tv]["results"]) != len(tv.rules.all()):
                api_o["messages"].append("Refusing to create QC report as not all target metrics could be assessed...")
                api_o["metrics"] = metrics
                api_o["errors"] += 1
                return

            curr_test_fails = 0
            for decision in tv.decisions.all():
                curr_dec = {
                    "decision": decision,
                    "a": None,
                    "b": None,
                    "is_pass": None,
                    "is_warn": None,
                    "is_fail": None,
                }

                results = test_data[tv]["results"]
                if decision.a not in results:
                    api_o["messages"].append("Could not make a decision for rule as metric appears to have not been selecting for testing")
                    api_o["errors"] += 1
                    return

                curr_dec["a"] = decision.a
                if not decision.b:
                    curr_dec["is_warn"] = results[decision.a]["is_warn"]
                    curr_dec["is_fail"] = results[decision.a]["is_fail"]
                else:
                    curr_dec["b"] = decision.b
                    if decision.b not in results:
                        api_o["messages"].append("Could not make a decision for rule as metric appears to have not been selecting for testing")
                        api_o["errors"] += 1
                        return
                    if decision.op == "AND":
                        curr_dec["is_warn"] = results[decision.a]["is_warn"] or results[decision.a]["is_warn"] # Warnings always roll up
                        curr_dec["is_fail"] = results[decision.a]["is_fail"] and results[decision.b]["is_fail"]
                    elif decision.op == "OR":
                        curr_dec["is_warn"] = results[decision.a]["is_warn"] or results[decision.a]["is_warn"]
                        curr_dec["is_fail"] = results[decision.a]["is_fail"] or results[decision.b]["is_fail"]
                    else:
                        api_o["messages"].append("Unknown decision operator encountered")
                        api_o["errors"] += 1
                        return
                curr_dec["is_pass"] = not curr_dec["is_fail"]
                if not curr_dec["is_pass"]:
                    n_fails += 1
                    curr_test_fails += 1
                test_data[tv]["decisions"][decision] = curr_dec
            test_data[tv]["is_pass"] = curr_test_fails == 0

            if len(test_data[tv]["decisions"]) != len(tv.decisions.all()):
                api_o["messages"].append("Refusing to create QC report as not all target metrics could be assessed...")
                api_o["errors"] += 1
                return

        if all_skipped:
            # See https://github.com/COG-UK/dipi-group/issues/55 for why we default to using at least one QC test
            api_o["messages"].append("Cowardly refusing to create QC report as no tests were performed...")
            api_o["errors"] += 1
            return

        # Looks good?
        tz_now_dt = timezone.now()
        is_pass = n_fails == 0
        ereport_g, created = models.PAGQualityReportEquivalenceGroup.objects.get_or_create(
                pag = pag,
                test_group = t_group,
        )
        ereport_g.last_updated = tz_now_dt
        ereport_g.is_pass = is_pass
        ereport_g.save()

        for tv in test_data:
            report_g, created = models.PAGQualityReportGroup.objects.get_or_create(
                    pag = pag,
                    group = ereport_g,
                    test_set = tv.test,
            )
            report_g.is_pass = test_data[tv]["is_pass"]
            report_g.is_skip = test_data[tv]["is_skip"]
            report_g.save()
            report, created = models.PAGQualityReport.objects.get_or_create(
                    report_group = report_g,
                    test_set_version = tv,
                    is_pass = test_data[tv]["is_pass"],
                    is_skip = test_data[tv]["is_skip"],
                    timestamp = tz_now_dt,
            )
            report.save()

            if test_data[tv]["is_skip"]:
                continue

            saved_rules = {}
            for rule, rule_result in test_data[tv]["results"].items():
                rule_result["report"] = report
                rule_rec, created = models.PAGQualityReportRuleRecord.objects.get_or_create(
                        **rule_result
                )
                rule_rec.save()
                saved_rules[rule] = rule_rec

            for decision, decision_result in test_data[tv]["decisions"].items():
                decision_result["report"] = report
                decision_result["a"] = saved_rules[decision_result["a"]]

                if decision_result["b"]:
                    decision_result["b"] = saved_rules[decision_result["b"]]
                dec_rec, created = models.PAGQualityReportDecisionRecord.objects.get_or_create(
                        **decision_result
                )
                dec_rec.save()

        api_o["test_results"] = str(test_data)
    return wrap_api_v2(request, f, oauth_permission="majora2.add_pagqualityreport majora2.change_pagqualityreport")

def add_metrics(request):
    def f(request, api_o, json_data, user=None, partial=False):

        artifact = json_data.get("artifact", "")
        artifact_path = json_data.get("artifact_path", "")

        if (not artifact or len(artifact) == 0) and (not artifact_path or len(artifact_path) == 0):
            api_o["messages"].append("'artifact' or 'artifact_path' key missing or empty")
            api_o["errors"] += 1
            return

        metrics = json_data.get("metrics", {})

        a = None
        if artifact:
            try:
                a = models.MajoraArtifact.objects.get(dice_name=artifact)
            except:
                pass
        elif artifact_path:
            #TODO Need a much better way to keep track of paths
            a = models.DigitalResourceArtifact.objects.filter(current_path=artifact_path).first()

        if not a:
            api_o["ignored"].append((artifact, artifact_path))
            api_o["errors"] += 1
            return

        for metric in metrics:
            metrics[metric]["artifact"] = a.id
            metrics[metric]["namespace"] = metric
            if metric == "sequence":
                m = models.TemporaryMajoraArtifactMetric_Sequence.objects.filter(artifact=a).first()
                form = forms.M2Metric_SequenceForm(metrics[metric], instance=m)
            elif metric == "mapping":
                m = models.TemporaryMajoraArtifactMetric_Mapping.objects.filter(artifact=a).first()
                form = forms.M2Metric_MappingForm(metrics[metric], instance=m)
            elif metric == "tile-mapping":
                m = models.TemporaryMajoraArtifactMetric_Mapping_Tiles.objects.filter(artifact=a).first()
                form = forms.M2Metric_MappingTileForm(metrics[metric], instance=m)
            else:
                api_o["ignored"].append(metric)
                api_o["messages"].append("'%s' does not describe a valid metric" % metric)
                api_o["warnings"] += 1
                continue

            if form.is_valid():
                try:
                    metric = form.save()
                    if metric:
                        api_o["updated"].append(_format_tuple(a))
                    else:
                        api_o["ignored"].append(metric)
                        api_o["errors"] += 1
                except Exception as e:
                    api_o["errors"] += 1
                    api_o["messages"].append(str(e))
            else:
                api_o["errors"] += 1
                api_o["ignored"].append(metric)
                api_o["messages"].append(form.errors.get_json_data())
    return wrap_api_v2(request, f)


# NOTE samstudio8 2021-05-25
# This endpoint was initially a workaround to support biosamples without metadata
# and allow downstream processes depending on them to be submitted without error,
# with the metadata to be filled in later. Today we extend this idea to optionally
# allow for a sender_sample_id to be pushed in to provide linkage to the four nations.
# This is a bit of a hack and with a little more time and energy I might've come up
# with a solution wherein the MajoraArtifact model itself has the ability to flag
# itself as a complete record or not. Nevertheless, we are not in the business to
# sit around and come up with elegant things and it just has to work instead.
# See https://github.com/COG-UK/dipi-group/issues/78
def addempty_biosample(request):
    def f(request, api_o, json_data, user=None, partial=False):
        biosamples = json_data.get("biosamples", [])
        if not biosamples:
            api_o["messages"].append("'biosamples' key missing or empty")
            api_o["errors"] += 1
            return

        if not isinstance(biosamples, list):
            api_o["errors"] += 1
            api_o["messages"].append("'biosamples' appears malformed")
            return

        for sample_id in biosamples:
            try:
                sender_sample_id = None
                if isinstance(sample_id, dict):
                    central_sample_id = sample_id["central_sample_id"]
                    sender_sample_id = sample_id.get("sender_sample_id")
                elif isinstance(sample_id, str):
                    central_sample_id = sample_id
                else:
                    raise Exception()
            except:
                api_o["warnings"] += 1
                api_o["messages"].append("'biosamples' appears malformed")
                continue

            # Make dummy sample
            biosample, created = models.BiosampleArtifact.objects.get_or_create(
                    central_sample_id=central_sample_id,
                    dice_name=central_sample_id,
            )
            if created:
                TatlVerb(request=request.treq, verb="CREATE", content_object=biosample).save()
                api_o["new"].append(_format_tuple(biosample))

                # Add the optional sender_sample_id ONLY if this sample was created,
                # no sneaky --partials possible here!
                if sender_sample_id:
                    biosample.sender_sample_id = sender_sample_id
            else:
                api_o["ignored"].append(_format_tuple(biosample))
                api_o["warnings"] += 1
            if not biosample.created:
                sample_p = models.BiosourceSamplingProcess()
                sample_p.save()
                sampling_rec = models.BiosourceSamplingProcessRecord(
                    process=sample_p,
                    out_artifact=biosample,
                )
                sampling_rec.save()
                biosample.created = sample_p # Set the sample collection process
                biosample.save()

    return wrap_api_v2(request, f, permission="majora2.force_add_biosampleartifact", oauth_permission="majora2.force_add_biosampleartifact majora2.add_biosampleartifact majora2.change_biosampleartifact majora2.add_biosourcesamplingprocess majora2.change_biosourcesamplingprocess", oauth_only=True)


class MajoraEndpointView(View):

    #TODO Abstract basic empty key checking to MEV
    #TODO Abstract wrap_api_v2 here
    #TODO Abstract tatl messages out of f to class

    def update(self, request, *args, **kwargs):
        #TODO Get objects to update to pass to f
        #TODO Set self.partial
        pass

    def create(self, request, *args, **kwargs):
        pass

    def retrieve(self, request, *args, **kwargs):
        pass

    def post(self, request, *args, **kwargs):
        api_tail = request.resolver_match.view_name.split('.')[-1]
        if api_tail == "add":
            return self.create(request, *args, **kwargs)
        elif api_tail == "update":
            return self.update(request, *args, **kwargs)


class BiosampleArtifactEndpointView(MajoraEndpointView):

    def create(self, request, *args, **kwargs):
        return wrap_api_v2(request, self.f, oauth_permission="majora2.add_biosampleartifact majora2.change_biosampleartifact majora2.add_biosamplesource majora2.change_biosamplesource majora2.add_biosourcesamplingprocess majora2.change_biosourcesamplingprocess")

    def update(self, request, *args, **kwargs):
        return wrap_api_v2(request, self.f, oauth_permission="majora2.change_biosampleartifact majora2.add_biosamplesource majora2.change_biosamplesource majora2.change_biosourcesamplingprocess", partial=True)

    def f(self, request, api_o, json_data, user=None, partial=False):
        biosamples = json_data.get("biosamples", {})
        if not biosamples:
            api_o["messages"].append("'biosamples' key missing or empty")
            api_o["errors"] += 1

        for biosample in biosamples:
            try:
                sample_id = biosample.get("central_sample_id")
                initial = fixed_data.fill_fixed_data("api.artifact.biosample.add", user)

                # Fetch objects for update (if applicable)
                supp = None
                sample_p = None
                source = None
                bs = models.BiosampleArtifact.objects.filter(central_sample_id=sample_id).first()
                if bs:
                    if hasattr(bs, "created"):
                        sample_p = bs.created
                    if hasattr(bs.created, "coguk_supp"):
                        supp = bs.created.coguk_supp
                    if hasattr(bs, "primary_group"):
                        source = bs.primary_group

                if partial:
                    if not bs:
                        api_o["errors"] += 1
                        api_o["ignored"].append(sample_id)
                        api_o["messages"].append("Cannot use `partial` on new BiosampleArtifact %s" % sample_id)
                        continue
                    if not sample_p or not sample_p.submission_user:
                        api_o["errors"] += 1
                        api_o["ignored"].append(sample_id)
                        api_o["messages"].append("Cannot use `partial` on empty BiosampleArtifact %s" % sample_id)
                        continue

                # Pre screen the cog uk supplementary form
                coguk_supp_form = forms.COGUK_BiosourceSamplingProcessSupplement_ModelForm(biosample, initial=initial, instance=supp, partial=partial)
                if not coguk_supp_form.is_valid():
                    api_o["errors"] += 1
                    api_o["ignored"].append(sample_id)
                    api_o["messages"].append(coguk_supp_form.errors.get_json_data())
                    continue

                # Pre screen the sample collection process form
                sample_process_form = forms.BiosourceSamplingProcessModelForm(biosample, initial=initial, instance=sample_p, partial=partial)
                if not sample_process_form.is_valid():
                    api_o["errors"] += 1
                    api_o["ignored"].append(sample_id)
                    api_o["messages"].append(sample_process_form.errors.get_json_data())
                    continue

                # Handle new sample
                sample_form = forms.BiosampleArtifactModelForm(biosample, initial=initial, instance=bs, partial=partial)
                if not sample_form.is_valid():
                    api_o["errors"] += 1
                    api_o["ignored"].append(sample_id)
                    api_o["messages"].append(sample_form.errors.get_json_data())
                    continue

                # Hit it
                sample = sample_form.save(commit=False)
                if not sample:
                    api_o["errors"] += 1
                    api_o["ignored"].append(sample_id)
                    continue

                # Create (or fetch) the biosample source (host)
                #TODO There is a form for this but it seems overkill for one field
                source_created = None
                biosample_source_id = biosample.get("biosample_source_id")
                if biosample_source_id:
                    source, source_created = models.BiosampleSource.objects.get_or_create(
                            dice_name=biosample_source_id,
                            secondary_id=biosample_source_id,
                            source_type = initial.get("source_type"), # previously fetched from form
                            physical=True,
                    )
                    source.save()

                # Create and save the sample collection process
                sample_p = sample_process_form.save(commit=False)
                if not sample_p.who:
                    submission_org = user.profile.institute if hasattr(user, "profile") and not user.profile.institute.code.startswith("?") else None
                    if submission_org:
                        sample_p.submitted_by = submission_org.name
                        sample_p.submission_org = submission_org
                    sample_p.who = user
                    sample_p.when = sample_p.collection_date if sample_p.collection_date else sample_p.received_date
                    sample_p.submission_user = user
                sample_p.save()

                # Update remaining sample fields
                sample.dice_name = sample.central_sample_id
                sample.primary_group = source
                sample.save()

                # Bind sample and sample collection process if sample_p is new
                if not sample.created:
                    sample.created = sample_p
                    if sample_p.records.count() == 0:
                        sampling_rec = models.BiosourceSamplingProcessRecord(
                            process=sample_p,
                            in_group=sample.primary_group,
                            out_artifact=sample,
                        )
                        sampling_rec.save()
                    sample.save()

                # Create and link the supplementary model data
                coguk_supp = coguk_supp_form.save(commit=False)
                coguk_supp.sampling = sample.created
                coguk_supp.save()

                # Hack to fix source if it has been changed at some point
                #TODO This only works in the cog context where we can assume 1:1 between sample and collection
                if source and sample.created:
                    for record in sample.created.records.all():
                        if record.in_group != source and record.out_artifact == sample:
                            record.in_group = source
                            record.save()

                updated_metadata_l = handle_metadata(biosample.get("metadata", {}), 'artifact', sample.dice_name, user, api_o)
                updated_metrics_l = handle_metrics(biosample.get("metrics", {}), 'artifact', sample, user, api_o) #TODO clean this as it duplicates the add_metric view

                if not bs and sample:
                    # Created
                    if api_o:
                        api_o["new"].append(_format_tuple(sample))
                        TatlVerb(request=request.treq, verb="CREATE", content_object=sample).save()
                else:
                    changed_data_d = forms.MajoraPossiblePartialModelForm.merge_changed_data(
                            coguk_supp_form, sample_process_form, sample_form
                    )
                    changed_data_d["changed_metadata"] = updated_metadata_l
                    changed_data_d["flashed_metrics"] = updated_metrics_l

                    if api_o:
                        api_o["updated"].append(_format_tuple(sample))
                        TatlVerb(request=request.treq, verb="UPDATE", content_object=sample, extra_context=json.dumps(changed_data_d)).save()
                if source_created:
                    if api_o:
                        api_o["new"].append(_format_tuple(source))
                        TatlVerb(request=request.treq, verb="CREATE", content_object=source).save()

            except Exception as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))


def add_library(request):
    def f(request, api_o, json_data, user=None, partial=False):
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
                library, library_created = form_handlers.handle_testlibrary(form, user=user, api_o=api_o, request=request)
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

        if not library:
            return
        try:
            handle_metadata(json_data.get("metadata", {}), 'artifact', library_name, user, api_o)
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

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
                    TatlVerb(request=request.treq, verb="CREATE", content_object=biosample).save()
                    api_o["new"].append(_format_tuple(biosample))
                    api_o["warnings"] += 1
                    sample_forced = True
                if not biosample.created:
                    sample_p = models.BiosourceSamplingProcess()
                    sample_p.save()
                    sampling_rec = models.BiosourceSamplingProcessRecord(
                        process=sample_p,
                        out_artifact=biosample,
                    )
                    sampling_rec.save()
                    biosample.created = sample_p # Set the sample collection process
                    biosample.save()
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
                    record, record_created = form_handlers.handle_testlibraryrecord(form, user=user, api_o=api_o, request=request)
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

    return wrap_api_v2(request, f, oauth_permission="majora2.add_biosampleartifact majora2.change_biosampleartifact majora2.add_libraryartifact majora2.change_libraryartifact majora2.add_librarypoolingprocess majora2.change_librarypoolingprocess")

def add_sequencing(request):
    def f(request, api_o, json_data, user=None, partial=False):
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


        # Try and get the library_name before the form does to provide a better
        # error for users submitting data from the online workflow
        try:
            models.LibraryArtifact.objects.get(dice_name=library_name)
        except:
            api_o["messages"].append({"library_name": [{"message": "Could not add sequencing to Library %s as it does not exist. Check and fix errors in your library fields and resubmit." % library_name, "code": ""}]})
            api_o["errors"] += 1
            return


        # Add sequencing runs to library
        for run in runs:
            try:
                run = forms.TestSequencingForm.modify_preform(run)
                initial = fixed_data.fill_fixed_data("api.process.sequencing.add", user)
                run["library_name"] = library_name
                run["run_group"] = json_data.get("run_group")
                form = forms.TestSequencingForm(run, initial=initial)
                if form.is_valid():
                    form.cleaned_data.update(initial)
                    sequencing, sequencing_created = form_handlers.handle_testsequencing(form, user=user, api_o=api_o, request=request)
                else:
                    api_o["errors"] += 1
                    api_o["messages"].append(form.errors.get_json_data())
            except Exception as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))

    return wrap_api_v2(request, f, oauth_permission="majora2.change_libraryartifact majora2.add_dnasequencingprocess majora2.change_dnasequencingprocess")

def add_digitalresource(request):
    def f(request, api_o, json_data, user=None, partial=False):

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
                mfile, created = form_handlers.handle_testdigitalresource(form, user=user, api_o=api_o, request=request)
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

    return wrap_api_v2(request, f, oauth_permission="majora2.add_digitalresourceartifact majora2.change_digitalresourceartifact")


def add_tag(request):
    def f(request, api_o, json_data, user=None, partial=False):

        if json_data.get("artifact"):
            handle_metadata(json_data.get("metadata", {}), 'artifact', json_data.get("artifact"), user, api_o)
        elif json_data.get("group"):
            handle_metadata(json_data.get("metadata", {}), 'group', json_data.get("group"), user, api_o)
        elif json_data.get("process"):
            handle_metadata(json_data.get("metadata", {}), 'process', json_data.get("process"), user, api_o)

    return wrap_api_v2(request, f)

def add_pag_accession(request):
    def f(request, api_o, json_data, user=None, partial=False):
        pag_name = json_data.get("publish_group")
        pag_contains = json_data.get("contains")
        if not pag_name:
            api_o["messages"].append("'publish_group' key missing or empty")
            api_o["errors"] += 1
            return

        if pag_contains:
            qs = models.PublishedArtifactGroup.objects.filter(published_name__contains=pag_name, is_latest=True, is_suppressed=False)
        else:
            qs = models.PublishedArtifactGroup.objects.filter(published_name=pag_name, is_latest=True, is_suppressed=False)

        if qs.count() > 1:
            api_o["messages"].append("%s does not uniquely identify a PAG in Majora" % pag_name)
            api_o["errors"] += 1
            return
        pag = qs.first()

        if not pag:
            api_o["messages"].append("PAG %s not known to Majora" % pag_name)
            api_o["errors"] += 1
            return

        if not json_data.get("service"):
            api_o["messages"].append("'service' key missing or empty")
            api_o["errors"] += 1
            return

        if not json_data.get("accession") and json_data.get("public"):
            api_o["messages"].append("You are trying to mark this PAG as public, but the 'accession' key is missing or empty.")
            api_o["errors"] += 1
            return

        accession, created = models.TemporaryAccessionRecord.objects.get_or_create(
                pag = pag,
                service = json_data.get("service"),
        )
        if accession:
            accession.primary_accession = json_data.get("accession")
            accession.secondary_accession = json_data.get("accession2")
            accession.tertiary_accession = json_data.get("accession3")
            accession.save()
            if api_o:
                api_o["updated"].append(_format_tuple(pag))

            if not accession.requested_timestamp and json_data.get("submitted"):
                accession.requested_timestamp = timezone.now()
                accession.requested_by = user
                accession.save()

            if json_data.get("public") and not accession.is_public:
                accession.is_public = True
                accession.public_timestamp = timezone.now()
                accession.save()
            if json_data.get("public") and json_data.get("public_date"):
                try:
                    accession.public_timestamp = datetime.datetime.strptime(json_data.get("public_date"), '%Y-%m-%d')
                    accession.save()
                except:
                    api_o["warnings"] += 1
                    api_o["messages"].append("Failed to coerce --public-date %s to a date." % json_data.get("public_date"))

            if json_data.get("public") and not pag.is_public:
                pag.is_public = True
                pag.public_timestamp = timezone.now()
                pag.save()
                api_o["messages"].append("PAG marked as public")

    return wrap_api_v2(request, f, oauth_permission="majora2.add_temporaryaccessionrecord majora2.change_temporaryaccessionrecord")

def get_outbound_summary(request):
    def f(request, api_o, json_data, user=None, partial=False):
        from django.db.models import Count, F, Q
        from dateutil.rrule import rrule, DAILY, WEEKLY, MO

        service = json_data.get("service")
        if not service or len(service) == 0:
            api_o["errors"] += 1
            api_o["messages"].append("'service' key missing or empty")
            return

        #status = json_data.get("status")
        #if not status or len(status) == 0:
        #    api_o["errors"] += 1
        #    api_o["messages"].append("'status' key missing or empty")
        #    return
        #
        #statuses = ["public", "submitted", "rejected"]
        #if status.lower() not in statuses:
        #    api_o["errors"] += 1
        #    api_o["messages"].append("'status' must be one of: %s" % str(statuses))
        #    return

        gte_date = None
        if json_data.get("gte_date"):
            try:
                gte_date = datetime.datetime.strptime(json_data.get("gte_date", ""), "%Y-%m-%d")
            except:
                api_o["errors"] += 1
                api_o["messages"].append("Could not convert %s to date." % json_data.get("gte_date"))
                return

        accessions = models.TemporaryAccessionRecord.objects.filter(service=service)
        api_o["get"] = {}
        api_o["get"]["intervals"] = []
        api_o["get"]["accessions"] = accessions.count()

        if json_data.get("user"):
            try:
                p = models.Profile.objects.get(user__username=json_data.get("user"))
                accessions = accessions.filter(requested_by=p.user)
            except:
                api_o["errors"] += 1
                api_o["messages"].append("Could not find named user.")
                return

        #interval_ends = list(rrule(WEEKLY, wkst=MO, dtstart=gte_date, until=timezone.now().date(), byweekday=MO))
        interval_ends = list(rrule(DAILY, wkst=MO, dtstart=gte_date, until=timezone.now().date()))
        for i in range(len(interval_ends)):
            submitted_accessions = accessions
            rejected_accessions = accessions.filter(is_rejected=True)
            published_accessions = accessions.filter(is_public=True)
            dt = interval_ends[i].date()
            last_dt = None
            if i == 0:
                # Everything before the date
                submitted_accessions = submitted_accessions.filter(requested_timestamp__date__lte=dt)
                rejected_accessions = rejected_accessions.filter(rejected_timestamp__date__lte=dt)
                published_accessions = published_accessions.filter(public_timestamp__date__lte=dt)
            else:
                # Everything between the last date and current date
                last_dt = interval_ends[i-1].date()
                submitted_accessions = submitted_accessions.filter(requested_timestamp__date__lte=dt, requested_timestamp__date__gt=last_dt)
                rejected_accessions = rejected_accessions.filter(rejected_timestamp__date__lte=dt, rejected_timestamp__date__gt=last_dt)
                published_accessions = published_accessions.filter(public_timestamp__date__lte=dt, public_timestamp__date__gt=last_dt)

            api_o["get"]["intervals"].append({
              "whole": True,
              "dt": dt.strftime("%Y-%m-%d"),
              "last_dt": last_dt.strftime("%Y-%m-%d") if last_dt else '',
              "submitted": submitted_accessions.count(),
              "rejected": rejected_accessions.count(),
              "released": published_accessions.count(),
            })

        # Tack on a final timestamp if the last time interval is not today
        if interval_ends[-1].date() != timezone.now().date():
            last_dt = interval_ends[-1].date() + datetime.timedelta(days=1)
            submitted_accessions = accessions
            rejected_accessions = accessions.filter(is_rejected=True)
            published_accessions = accessions.filter(is_public=True)
            submitted_accessions = submitted_accessions.filter(requested_timestamp__date__gt=last_dt)
            rejected_accessions = rejected_accessions.filter(rejected_timestamp__date__gt=last_dt)
            published_accessions = published_accessions.filter(public_timestamp__date__gt=last_dt)
            api_o["get"]["intervals"].append({
              "whole": False,
              "dt": timezone.now().date().strftime("%Y-%m-%d"),
              "last_dt": last_dt.strftime("%Y-%m-%d") if last_dt else '',
              "submitted": submitted_accessions.count(),
              "rejected": rejected_accessions.count(),
              "released": published_accessions.count(),
            })

    return wrap_api_v2(request, f)

def get_dashboard_metrics(request):
    def f(request, api_o, json_data, user=None, partial=False):
        from django.db.models import Count, F, Q, ExpressionWrapper, BooleanField, Subquery

        gte_date=None
        the_pags = models.PAGQualityReportEquivalenceGroup.objects.filter(test_group__slug="cog-uk-elan-minimal-qc", pag__is_latest=True, pag__is_suppressed=False)
        try:
            gte_date = datetime.datetime.strptime(json_data.get("gte_date", ""), "%Y-%m-%d")
            the_pags = the_pags.filter(last_updated__gt=gte_date)
        except:
            pass

        all_pags = {}
        for pag in the_pags.values(
                                   site=F('pag__owner__profile__institute__code'),
                                   sourcesite=F('pag__tagged_artifacts__biosampleartifact__created__who__profile__institute__code'),
                                   is_surveillance=ExpressionWrapper(F('pag__tagged_artifacts__biosampleartifact__created__biosourcesamplingprocess__coguk_supp__is_surveillance'), output_field=BooleanField()),
                           ) \
                           .exclude(sourcesite__isnull=True) \
                           .annotate(
                                     count=Count('pk'),
                                     failc=Count('pk', filter=Q(is_pass=False)),
                                     passc=Count('pk', filter=Q(is_pass=True)),
                                     surveillance_num=Count('pk', filter=Q(is_surveillance=True)),
                                     surveillance_dom=Count('pk', filter=Q(is_surveillance__isnull=False)),
                           ):

            if (pag["sourcesite"], pag["site"]) not in all_pags:
                all_pags[(pag["sourcesite"], pag["site"])] = {
                    'site': pag['site'],
                    'sourcesite': pag['sourcesite'],
                    'count': 0,
                    'surveillance_num': 0,
                    'surveillance_dom': 0,
                    'pass_count': 0,
                    'fail_count': 0,
                }
            all_pags[(pag["sourcesite"], pag["site"])]["count"] += pag["count"]
            all_pags[(pag["sourcesite"], pag["site"])]["pass_count"] += pag["passc"]
            all_pags[(pag["sourcesite"], pag["site"])]["fail_count"] += pag["failc"]
            all_pags[(pag["sourcesite"], pag["site"])]["surveillance_num"] += pag["surveillance_num"]
            all_pags[(pag["sourcesite"], pag["site"])]["surveillance_dom"] += pag["surveillance_dom"]


        api_o["get"] = {
            "total_sequences": models.PublishedArtifactGroup.objects.filter(is_latest=True, is_suppressed=False).count(),
            "site_qc": sorted(all_pags.values(), key=lambda x: x.get('count'), reverse=True),
        }
    return wrap_api_v2(request, f)


def get_pag_by_qc_celery(request):
    def f(request, api_o, json_data, user=None, partial=False):
        test_name = json_data.get("test_name")
        dra_current_kind = json_data.get("dra_current_kind")

        if not test_name or len(test_name) == 0:
            api_o["messages"].append("'test_name', key missing or empty")
            api_o["errors"] += 1
            return
        t_group = models.PAGQualityTestEquivalenceGroup.objects.filter(slug=test_name).first()
        if not t_group:
            api_o["messages"].append("Invalid 'test_name'")
            api_o["ignored"].append(test_name)
            api_o["errors"] += 1
            return

        from . import tasks
        basic_task = True
        get_mode = json_data.get("mode")
        if get_mode and len(get_mode) > 0:
            if get_mode.lower() == "ena-assembly":
                pass
            elif get_mode.lower() == "pagfiles":
                celery_task = tasks.task_get_pagfiles.delay(None, api_o, json_data, user=user.pk, response_uuid=api_o["request"])
                basic_task = False

        if basic_task:
            celery_task = tasks.task_get_pag_v2.delay(None, api_o, json_data, user=user.pk, response_uuid=api_o["request"])

        if celery_task:
            api_o["tasks"].append(celery_task.id)
            api_o["messages"].append("Call api.majora.task.get with the appropriate task ID later...")
        else:
            api_o["errors"] += 1
            api_o["messages"].append("Could not add requested task to Celery...")

    return wrap_api_v2(request, f, permission="majora2.temp_can_read_pags_via_api")

def stream_task_result(request):
    def f(request, api_o, json_data, user=None, partial=False):

        import requests, boto3
        from botocore.exceptions import ClientError

        task_id = json_data.get("task_id")
        if not task_id:
            api_o["messages"].append("'task_id' key missing or empty")
            api_o["errors"] += 1
            return

        from mylims.celery import app
        res = app.AsyncResult(task_id)
        if res.state == "SUCCESS":
            try:
                s3 = boto3.client('s3',
                        aws_access_key_id=settings.CELERY_S3_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.CELERY_S3_SECRET_ACCESS_KEY,
                        endpoint_url=settings.CELERY_S3_ENDPOINT_URL,
                        region_name=None,
                )

                purl = s3.generate_presigned_url('get_object',
                        Params={
                            'Bucket': settings.CELERY_S3_BUCKET,
                            'Key': app.backend.get_key_for_task(res.id).decode("utf-8"),
                        },
                        ExpiresIn=10,
                )

                r = requests.get(url=purl, stream=True)
                return StreamingHttpResponse(r.raw, content_type="application/json")

            except ClientError as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))
        else:
            api_o["warnings"] += 1
            api_o["messages"].append("Task is not (yet) SUCCESS...")

        api_o["task"] = {
            "id": task_id,
            "state": res.state,
        }

    return wrap_api_v2(request, f, stream=True)

def get_task_result(request):
    def f(request, api_o, json_data, user=None, partial=False):
        task_id = json_data.get("task_id")
        if not task_id:
            api_o["messages"].append("'task_id' key missing or empty")
            api_o["errors"] += 1
            return

        from mylims.celery import app
        res = app.AsyncResult(task_id)
        if res.state == "SUCCESS":
            try:
                api_o.update(res.get())
            except Exception as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))
        else:
            api_o["warnings"] += 1
            api_o["messages"].append("Task is not (yet) SUCCESS...")

        api_o["task"] = {
            "id": task_id,
            "state": res.state,
        }

    return wrap_api_v2(request, f)

def del_task_result(request):
    def f(request, api_o, json_data, user=None, partial=False):
        task_id = json_data.get("task_id")
        if not task_id:
            api_o["messages"].append("'task_id' key missing or empty")
            api_o["errors"] += 1
            return

        from mylims.celery import app
        res = app.AsyncResult(task_id)
        was_deleted = False
        if res.state == "SUCCESS":
            try:
                # Not sure wtf is going on here but the current version of celery s3 seems to bug out that k is bytes
                k = app.backend.get_key_for_task(res.id).decode("utf-8")
                app.backend.delete(k)
                api_o["deleted"] = k
                was_deleted = True
            except Exception as e:
                api_o["errors"] += 1
                api_o["messages"].append(str(e))
        else:
            api_o["warnings"] += 1
            api_o["messages"].append("Task is not (yet) SUCCESS...")

        api_o["task"] = {
            "id": task_id,
            "state": res.state,
            "deleted": was_deleted,
        }

    return wrap_api_v2(request, f)

def get_mag(request):
    def f(request, api_o, json_data, user=None, partial=False):
        path = json_data.get("path")
        sep = json_data.get("sep")

        if not path or len(path) == 0 or "://" not in path:
            api_o["messages"].append("'path' key missing, empty or malformed")
            api_o["errors"] += 1
            return

        node_name, path = path.split("://")
        mag = util.get_mag(node_name, path, by_hard_path=True)

        if not mag:
            api_o["messages"].append("Invalid path.")
            api_o["errors"] += 1
            return

        if (mag.children.count() > 100 or mag.groups.count() > 100 or mag.out_glinks.count() > 100) and not json_data.get("force"):
            api_o["messages"].append("This MAG contains more than 100 groups or artifacts.")
            api_o["error_code"] = "BIGMAG:%d" % max(mag.children.count(), mag.groups.count(), mag.out_glinks.count())
            api_o["errors"] += 1
            return


        from .serializers import MAGSerializer
        api_o["mag"] = MAGSerializer(mag).data

    return wrap_api_v2(request, f)

def suppress_pag(request):
    def f(request, api_o, json_data, user=None, partial=False):
        pag_names = json_data.get("publish_group")
        reason = json_data.get("reason")

        if (not pag_names) or (not reason):
            api_o["messages"].append("'publish_group' or 'reason' key missing or empty")
            api_o["errors"] += 1
            return
        if len(pag_names)==0 or len(reason)==0:
            api_o["messages"].append("'publish_group' or 'reason' key missing or empty")
            api_o["errors"] += 1
            return

        valid_reasons = ["WRONG_BARCODE", "WRONG_METADATA", "WRONG_SEQUENCE", "CONTROL_FAIL"]
        if reason.upper() not in valid_reasons:
            api_o["messages"].append("Reason must be one of: %s" % str(valid_reasons))
            api_o["errors"] += 1
            return

        if type(pag_names) == str:
            pag_names = [pag_names]

        for pag_name in pag_names:
            pag = models.PublishedArtifactGroup.objects.filter(is_latest=True, published_name=pag_name).first() # There can be only one
            if not pag:
                api_o["ignored"].append(pag_name)
                api_o["warnings"] += 1
                api_o["messages"].append("%s not found" % pag_name)
                continue

            if pag.is_suppressed:
                api_o["ignored"].append(pag_name)
                api_o["warnings"] += 1
                api_o["messages"].append("%s already suppressed" % pag_name)
                continue

            if pag.owner.profile.institute != user.profile.institute and not user.has_perm('majora2.can_suppress_pags_via_api'):
                api_o["ignored"].append(pag_name)
                api_o["errors"] += 1
                api_o["messages"].append("Your organisation (%s) does not own %s (%s)" % (user.profile.institute.code, pag_name, pag.owner.profile.institute.code))
                continue

            pag.is_suppressed = True
            pag.suppressed_date = timezone.now()
            pag.suppressed_reason = reason.upper()
            pag.save()
            api_o["updated"].append(_format_tuple(pag))
            TatlVerb(request=request.treq, verb="SUPPRESS", content_object=pag).save()

    return wrap_api_v2(request, f) # TODO Needs OAuth will fallback to Owner


def v0_get_artifact_info(request):
    def f(request, api_o, json_data, user=None, partial=False):
        query = None
        artifact = None
        query = request.GET.get("q", '')

        if not query or len(query) == 0:
            api_o["messages"].append("'q' GET param missing or empty")
            api_o["errors"] += 1
            return

        api_o["info"] = {}
        try:
            artifact = models.MajoraArtifact.objects.get(id=query)
        except Exception:
            pass

        if not artifact:
            try:
                artifact = models.MajoraArtifact.objects.get(dice_name=query)
            except Exception:
                pass

        # TODO Unify Artifact interface
        if not artifact:
            try:
                node_name, path = query.split("://")
                path = "/%s" % path # ???
                mag = util.get_mag(node_name, path, artifact=True, by_hard_path=False, prefetch=False) # not using hard path yet
                if mag:
                    artifact = models.DigitalResourceArtifact.objects.get(primary_group=mag, current_path=path)
            except Exception:
                pass

        if not artifact:
            try:
                artifact_fuzz = models.MajoraArtifact.objects.filter(dice_name__contains=query)
            except Exception:
                pass

            if artifact_fuzz.count() == 1:
                artifact = artifact_fuzz[0]


        if not artifact:
            api_o["errors"] += 1
            api_o["messages"].append("No artifact for query.")
            return

        try:
            api_o["info"] = artifact.info
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

    return wrap_api_v2(request, f, oauth_permission="majora2.view_majoraartifact_info", get=True)
#TODO False permission to disable v2
