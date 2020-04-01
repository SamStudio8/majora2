from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.db.models import Count
from django.db.models import F

from django.utils import timezone
from django.db.models.functions import TruncDay
import datetime

from . import models
from . import util

def sample_sequence_count_dashboard(request):
    collections = models.BiosourceSamplingProcess.objects.values("collected_by").annotate(Count("collected_by")).order_by("-collected_by__count")
    total_collections = models.BiosourceSamplingProcess.objects.count()

    consensii = models.DigitalResourceArtifact.objects.filter(current_kind="consensus").values(org=F("created__who__profile__institute__name")).annotate(count=Count("org"))
    total_consensii = models.DigitalResourceArtifact.objects.filter(current_kind="consensus").count()

    adm2 = models.BiosourceSamplingProcess.objects.all().values(adm2=F("collection_location_adm2")).annotate(count=Count("adm2")).order_by("adm2")

    consensus_spark = util.make_spark(models.DigitalResourceArtifact.objects.filter(created__when__isnull=False, created__when__gte=timezone.now().date()-datetime.timedelta(days=30)).annotate(date=TruncDay('created__when')).values("date").annotate(count=Count('id')).order_by("date"), days=30)


    return render(request, 'public/special/dashboard.html', {
        "collections": collections,
        "total_collections": total_collections,
        "sequences": consensii,
        "total_sequences": total_consensii,
        "adm2": adm2,
        "n_regions": len(adm2),

        "consensus_spark": consensus_spark,
    })
