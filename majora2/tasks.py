# Create your tasks here
from __future__ import absolute_import, unicode_literals

from celery import shared_task, current_task
from . import models
from . import serializers
from . import resty_serializers

from django.db.models import Q

import datetime

@shared_task
def structify_pags(api_o):
    # Return everything?
    api_o["get"] = {}
    api_o["get"]["result"] = serializers.PAGQCSerializer(models.PAGQualityReportEquivalenceGroup.objects.select_related('pag').prefetch_related('pag__tagged_artifacts').all(), many=True).data
    return api_o

@shared_task
def task_get_sequencing(request, api_o, json_data, user=None):
    run_names = json_data.get("run_name")
    if not run_names:
        api_o["messages"].append("'run_name' key missing or empty")
        api_o["errors"] += 1
        return

    if len(run_names) == 1 and run_names[0] == "*":
        #TODO Cannot check staff status here, relies on checking in the calling view.
        run_names = [run["run_name"] for run in models.DNASequencingProcess.objects.all().values("run_name")]

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

    try:
        api_o["get"] = {}
        api_o["get"]["result"] = runs
        api_o["get"]["count"] = len(runs)
    except Exception as e:
        api_o["errors"] += 1
        api_o["messages"].append(str(e))
    return api_o


@shared_task
def task_get_pag_by_qc(request, api_o, json_data, user=None, **kwargs):
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

    reports = models.PAGQualityReportEquivalenceGroup.objects.filter(test_group=t_group, pag__is_latest=True, pag__is_suppressed=False)

    if json_data.get("published_date"):
        try:
            gt_date = datetime.datetime.strptime(json_data.get("published_after", ""), "%Y-%m-%d")
            reports = reports.filter(pag__published_date__gt=gt_date)
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))

    if json_data.get("pass") and json_data.get("fail"):
        pass
    elif json_data.get("pass"):
        reports = reports.filter(is_pass=True)
    elif json_data.get("fail"):
        reports = reports.filter(is_pass=False)
    else:
        pass

    # Return only PAGs with the service name, otherwise use the is_pbulic shortcut
    if json_data.get("public") and json_data.get("private"):
        if json_data.get("service_name"):
            api_o["messages"].append("service_name is ignored with both public and private")
        pass
    elif json_data.get("public"):
        if json_data.get("service_name"):
            reports = reports.filter(pag__accessions__service=json_data.get("service_name"), pag__accessions__is_public=True)
        else:
            reports = reports.filter(pag__is_public=True)
    elif json_data.get("private"):
        if json_data.get("service_name"):
            # Exclude any PAG that has this service name (public or not)
            # Private means unsubmitted in this context basically
            reports = reports.filter(~Q(pag__accessions__service=json_data.get("service_name")))
        else:
            reports = reports.filter(pag__is_public=False)
    else:
        if json_data.get("service_name"):
            api_o["messages"].append("service_name is ignored without public or private")
        pass



    try:
        api_o["get"] = {}
        api_o["get"]["result"] = serializers.PAGQCSerializer(reports.select_related('pag').prefetch_related('pag__tagged_artifacts').all(), many=True).data
        api_o["get"]["count"] = len(reports)
    except Exception as e:
        api_o["errors"] += 1
        api_o["messages"].append(str(e))
    return api_o

@shared_task
def task_get_pag_by_qc_v3(pag_ids, context={}):
    queryset = models.PublishedArtifactGroup.objects.filter(id__in=pag_ids)
    serializer = resty_serializers.RestyPublishedArtifactGroupSerializer(queryset, many=True, context=context)

    api_o = {
        "data": serializer.data,
    }

    return api_o

@shared_task
def task_get_mdv_v3(ids, context={}, **kwargs):

    api_o = {
        "data": {},
    }

    return api_o
