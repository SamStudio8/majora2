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
import uuid
import datetime

MINIMUM_CLIENT_VERSION = "0.19.0"

@csrf_exempt
def wrap_api_v2(request, f, permission=None):
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

    # https://stackoverflow.com/questions/4581789/how-do-i-get-user-ip-address-in-django
    remote_addr = None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        remote_addr = x_forwarded_for.split(',')[0]
    else:
        remote_addr = request.META.get('REMOTE_ADDR')

    json_data = json.loads(request.body)
    treq = TatlRequest(
        user = None,
        substitute_user = None,
        route = request.path,
        payload = json_data,
        timestamp = timezone.now(),
        remote_addr = remote_addr,
        response_uuid = uuid.uuid4()
    )
    treq.save()
    api_o["request"] = str(treq.response_uuid)

    # Bounce non-POST
    if request.method != "POST":
        return HttpResponseBadRequest()

    # Bounce badly formatted requests
    if not json_data.get('token', None) or not json_data.get('username', None):
        return HttpResponseBadRequest()

    profile = None
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

    treq.user = user
    treq.save()

    if permission:
        tflex = TatlPermFlex(
            user = user,
            substitute_user = None,
            used_permission = permission,
            timestamp = timezone.now(),
            request=treq,
            content_object = treq, #TODO just use the request for now
        )
        tflex.save()

    # Bounce non-admin escalations to other users
    if json_data.get("sudo_as"):
        if user.is_staff:
            try:
                user = models.Profile.objects.get(user__username=json_data["sudo_as"]).user
                treq.substitute_user = user
                treq.save()

                if permission:
                    tflex.substitute_user = user
                    tflex.save()
            except:
                return HttpResponseBadRequest()
        else:
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
    if not bad and profile:
        f(request, api_o, json_data, user=user)

    api_o["success"] = api_o["errors"] == 0

    end_ts = timezone.now()
    treq.response_time = end_ts - start_ts
    treq.save()

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

#TODO Abstract this away info form handlers per-metric, use modelforms properly
def handle_metrics(metrics, tag_type, tag_to, user, api_o):
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
                    api_o["updated"].append(form_handlers._format_tuple(tag_to))

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
                                    api_o["messages"].append("%d existing Ct value records deleted and replaced with new values" % int(dc/2))
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





def get_biosample(request):
    def f(request, api_o, json_data, user=None):
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
    def f(request, api_o, json_data, user=None):
        run_names = json_data.get("run_name")
        if not run_names:
            api_o["messages"].append("'run_name' key missing or empty")
            api_o["errors"] += 1
            return

        if len(run_names) == 1 and run_names[0] == "*":
            if user.is_staff:
                from . import tasks
                celery_task = tasks.task_get_sequencing.delay(None, api_o, json_data, user=None)
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
    def f(request, api_o, json_data, user=None):
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
            for metric in artifact.temporarymajoraartifactmetric_set.all():
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
    return wrap_api_v2(request, f)

def add_metrics(request):
    def f(request, api_o, json_data, user=None):

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
                        api_o["updated"].append(form_handlers._format_tuple(a))
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

                biosample = forms.TestSampleForm.modify_preform(biosample)
                form = forms.TestSampleForm(biosample, initial=initial)
                if form.is_valid():
                    del initial["submitting_org"]
                    form.cleaned_data.update(initial)
                    sample, sample_created = form_handlers.handle_testsample(form, user=user, api_o=api_o)
                    if not sample:
                        api_o["ignored"].append(sample_id)
                        api_o["errors"] += 1
                    else:
                        handle_metadata(biosample.get("metadata", {}), 'artifact', sample.dice_name, user, api_o)
                        handle_metrics(biosample.get("metrics", {}), 'artifact', sample, user, api_o) #TODO clean this as it duplicates the add_metric view
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
                    api_o["new"].append(form_handlers._format_tuple(biosample))
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

def add_pag_accession(request):
    def f(request, api_o, json_data, user=None):
        pag_name = json_data.get("publish_group")
        pag_contains = json_data.get("contains")
        if not pag_name:
            api_o["messages"].append("'publish_group' key missing or empty")
            api_o["errors"] += 1
            return

        if pag_contains:
            qs = models.PublishedArtifactGroup.objects.filter(published_name__contains=pag_name, is_latest=True, is_suppressed=False)
            if qs.count() > 1:
                api_o["messages"].append("%s does not uniquely identify a PAG in Majora" % pag_name)
                api_o["errors"] += 1
                return
            pag = qs.first()
        else:
            pag = models.PublishedArtifactGroup.objects.get(published_name=pag_name, is_latest=True, is_suppressed=False)

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
                api_o["updated"].append(form_handlers._format_tuple(pag))

            if not accession.requested_timestamp and json_data.get("submitted"):
                accession.requested_timestamp = timezone.now()
                accession.requested_by = user
                accession.save()

            if json_data.get("public") and not accession.is_public:
                accession.is_public = True
                accession.public_timestamp = timezone.now()
                accession.save()

            if json_data.get("public") and not pag.is_public:
                pag.is_public = True
                pag.public_timestamp = timezone.now()
                pag.save()
                api_o["messages"].append("PAG marked as public")

    return wrap_api_v2(request, f)

def get_outbound_summary(request):
    def f(request, api_o, json_data, user=None):
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
    def f(request, api_o, json_data, user=None):
        from django.db.models import Count, F, Q

        gte_date=None
        the_pags = models.PAGQualityReportEquivalenceGroup.objects.filter(test_group__slug="cog-uk-elan-minimal-qc", pag__is_latest=True, pag__is_suppressed=False)
        try:
            gte_date = datetime.datetime.strptime(json_data.get("gte_date", ""), "%Y-%m-%d")
            the_pags = the_pags.filter(last_updated__gt=gte_date)
        except:
            pass

        the_pags = the_pags.values(site=F('pag__owner__profile__institute__code'), sourcesite=F('pag__tagged_artifacts__biosampleartifact__created__who__profile__institute__code')) \
                           .exclude(sourcesite__isnull=True) \
                           .annotate(
                                     count=Count('pk'),
                                     failc=Count('pk', filter=Q(is_pass=False)),
                                     passc=Count('pk', filter=Q(is_pass=True))) \
                           .order_by('-count')

        all_pags = [{
            'site': x['site'],
            'sourcesite': x['sourcesite'],
            'count': x['count'], 'pass_count': x['passc'], 'fail_count': x['failc'],
        } for x in the_pags]


        api_o["get"] = {
            "total_sequences": models.PublishedArtifactGroup.objects.filter(is_latest=True, is_suppressed=False).count(),
            "site_qc": all_pags,
        }
    return wrap_api_v2(request, f)



def get_pag_by_qc_celery(request):
    def f(request, api_o, json_data, user=None):
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
        celery_task = tasks.task_get_pag_by_qc.delay(None, api_o, json_data, user=user.pk, response_uuid=api_o["request"])
        if celery_task:
            api_o["tasks"].append(celery_task.id)
            api_o["messages"].append("Call api.majora.task.get with the appropriate task ID later...")
        else:
            api_o["errors"] += 1
            api_o["messages"].append("Could not add requested task to Celery...")

    return wrap_api_v2(request, f, permission="majora2.temp_can_read_pags_via_api")

def get_task_result(request):
    def f(request, api_o, json_data, user=None):
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
    def f(request, api_o, json_data, user=None):
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
    def f(request, api_o, json_data, user=None):
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
            api_o["warnings"] += 1
            return

        api_o["mag"] = {
            "name": mag.current_name,
            "children": [(str(m.id), m.name, [(a.artifact_kind, a.name, a.current_path if hasattr(a, 'current_path') else '') for a in m.tagged_artifacts.all()]) for m in mag.children.all()],
            "links": [(str(m.id), m.name, [(a.artifact_kind, a.name, a.current_path if hasattr(a, 'current_path') else '') for a in m.tagged_artifacts.all()]) for m in mag.groups.all()],
        }

    return wrap_api_v2(request, f)
