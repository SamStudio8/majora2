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
    import serpy
    class ArtifactSerializer(serpy.Serializer):
        id = serpy.StrField()
        dice_name = serpy.StrField()
        artifact_kind = serpy.StrField()
    class DigitalResourceArtifactSerializer(ArtifactSerializer):
        current_path = serpy.StrField()
        current_name = serpy.StrField()
        current_kind = serpy.StrField()
    class PAGSerializer(serpy.Serializer):
        id = serpy.StrField()
        published_name = serpy.StrField()
        published_version = serpy.IntField()
        published_date = serpy.MethodField('serialize_published_date')

        #tagged_artifacts = ArtifactSerializer(many=True, attr='tagged_artifacts.all', call=True)
        tagged_artifacts = serpy.MethodField('serialize_tagged_artifacts')

        def serialize_tagged_artifacts(self, pag):
            a = []
            for artifact in pag.tagged_artifacts.all():
                if artifact.artifact_kind == "Digital Resource":
                    a.append(DigitalResourceArtifactSerializer(artifact).data)
                else:
                    a.append(ArtifactSerializer(artifact).data)
            return a

        def serialize_published_date(self, pag):
            return pag.published_date.isoformat()
    class PAGQCSerializer(serpy.Serializer):
        id = serpy.StrField()
        pag = PAGSerializer()

    #pags = {}
    #for test_report in models.PAGQualityReportEquivalenceGroup.objects.select_related('pag').prefetch_related('pag__tagged_artifacts').all():
    #    try:
    #        pags[test_report.pag.published_name] = test_report.pag.as_struct()
    #        pags[test_report.pag.published_name]["status"] = "PASS" if test_report.is_pass else "FAIL"
    #    except Exception as e:
    #        api_o["errors"] += 1
    #        api_o["messages"].append(str(e))
    #        continue
    #api_o["get"] = pags
    api_o["get"] = PAGQCSerializer(models.PAGQualityReportEquivalenceGroup.objects.select_related('pag').prefetch_related('pag__tagged_artifacts').all(), many=True).data

    signals.task_end.send(sender=current_task.request, task="structify_pags", task_id=current_task.request.id)
    return api_o
