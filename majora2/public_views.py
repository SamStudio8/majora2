from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.db.models import Count
from django.db.models import F
from django.views.decorators.cache import cache_page

from django.utils import timezone
from django.db.models.functions import TruncDay
import datetime

from . import models
from . import util

@cache_page(60 * 60)
def sample_sequence_count_dashboard(request):
    collections = models.BiosourceSamplingProcess.objects.values("collected_by").annotate(Count("collected_by")).order_by("-collected_by__count")
    total_collections = models.BiosourceSamplingProcess.objects.count()

    adm2 = models.BiosourceSamplingProcess.objects.all().values(adm2=F("collection_location_adm2")).annotate(count=Count("adm2")).order_by("adm2")

    consensus_spark = util.make_spark(models.DigitalResourceArtifact.objects.filter(created__when__isnull=False, created__when__gte=timezone.now().date()-datetime.timedelta(days=30)).annotate(date=TruncDay('created__when')).values("date").annotate(count=Count('id')).order_by("date"), days=30)

    #consensus_spark = util.make_spark(models.DNASequencingProcess.objects.filter(when__gte=timezone.now().date()-datetime.timedelta(days=30)).annotate(date=TruncDay('when')).values("date").annotate(count=Count('id')).order_by("date"), days=30)
    #total_consensii = models.DNASequencingProcess.objects.count()

    total_c = 0
    sites = {}
    for c in models.DigitalResourceArtifact.objects.filter(current_kind="consensus"):
        site_name = c.created.who.profile.institute.name
        if site_name not in sites:
            sites[site_name] = {"count": 0, "public": 0, "site": site_name}
        sites[site_name]["count"] += 1
        total_c += 1

        is_public = c.cogtemp_get_public
        if is_public == '1': # its a string lolololol ffs
            sites[site_name]["public"] += 1

    return render(request, 'public/special/dashboard.html', {
        #"collections": collections,
        "total_collections": total_collections,
        "new_sequences": sorted(sites.items(), key=lambda x: x[1]["count"], reverse=True),
        "total_sequences": total_c,
        "adm2": adm2,
        "n_regions": len(adm2),

        "consensus_spark": consensus_spark,
    })
