# Create your tasks here
from __future__ import absolute_import, unicode_literals

from celery import shared_task, current_task
from . import models
from . import signals


@shared_task
def add(x, y):
    return x + y


@shared_task
def mul(x, y):
    return x * y


@shared_task
def xsum(numbers):
    return sum(numbers)


@shared_task
def count_widgets():
    return models.PublishedArtifactGroup.objects.count()

@shared_task
def structify_pags(api_o):
    # Return everything?
    pags = {}
    for test_report in models.PAGQualityReportEquivalenceGroup.objects.all():
        try:
            pags[test_report.pag.published_name] = test_report.pag.as_struct()
            pags[test_report.pag.published_name]["status"] = "PASS" if test_report.is_pass else "FAIL"
        except Exception as e:
            api_o["errors"] += 1
            api_o["messages"].append(str(e))
            continue
    api_o["get"] = pags

    signals.task_end.send(sender=current_task.request, task="structify_pags", task_id=current_task.request.id)
    return api_o
