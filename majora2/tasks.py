# Create your tasks here
from __future__ import absolute_import, unicode_literals

from celery import shared_task, current_task
from . import models
from . import signals
from . import serializers

import datetime

@shared_task
def structify_pags(api_o):
    # Return everything?
    api_o["get"] = {}
    api_o["get"]["result"] = serializers.PAGQCSerializer(models.PAGQualityReportEquivalenceGroup.objects.select_related('pag').prefetch_related('pag__tagged_artifacts').all(), many=True).data
    signals.task_end.send(sender=current_task.request, task="structify_pags", task_id=current_task.request.id)
    return api_o

@shared_task
def task_get_pag_by_qc(request, api_o, json_data, user=None):
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

    if json_data.get("public") and json_data.get("private"):
        pass
    elif json_data.get("public"):
        reports = reports.filter(pag__is_public=True)
    elif json_data.get("private"):
        reports = reports.filter(pag__is_public=False)
    else:
        pass

    try:
        api_o["get"] = {}
        api_o["get"]["result"] = serializers.PAGQCSerializer(reports.select_related('pag').prefetch_related('pag__tagged_artifacts').all(), many=True).data
        api_o["get"]["count"] = len(reports)
    except Exception as e:
        api_o["errors"] += 1
        api_o["messages"].append(str(e))
    signals.task_end.send(sender=current_task.request, task="structify_pags", task_id=current_task.request.id)
    return api_o
