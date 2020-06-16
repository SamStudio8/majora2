from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.db.models import Count, F, Q
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator

from django.utils import timezone
from django.db.models.functions import TruncDay
import datetime

from . import models
from tatl import models as tmodels
from . import util

from django_datatables_view.base_datatable_view import BaseDatatableView

class OrderListJson(BaseDatatableView):
    model = models.PublishedArtifactGroup

    columns = ["id", "published_name", "published_date", "GISAID", "ENA"]
    order_columns = ["id", "published_name", "published_date", "-", "-"]
    max_display_length = 100

    def render_column(self, row, column):
        if column == "GISAID":
            ass = row.accessions.filter(service="GISAID").first()
            if ass:
                return ass.primary_accession
            else:
                return "-"
        elif column == "ENA":
            ass = row.accessions.filter(service="ENA-RUN").first()
            if ass:
                return ass.primary_accession
            else:
                return "-"
        else:
            return super(OrderListJson, self).render_column(row, column)

    def filter_queryset(self, qs):
        search = self.request.GET.get('search[value]', None)
        if search:
            qs = qs.filter(published_name__contains=search)
        return qs

@cache_page(60 * 60)
def list_accessions(request):
    return render(request, 'public/special/pag_list.html', {})


@cache_page(60 * 60)
def sample_sequence_count_dashboard(request):
    collections = models.BiosourceSamplingProcess.objects.values("collected_by").annotate(Count("collected_by")).order_by("-collected_by__count")
    total_collections = models.BiosourceSamplingProcess.objects.count()

    adm2 = models.BiosourceSamplingProcess.objects.all().values(adm2=F("collection_location_adm2")).annotate(count=Count("adm2")).order_by("adm2")

    consensus_spark = util.make_spark(models.DigitalResourceArtifact.objects.filter(current_kind="consensus", created__when__isnull=False, created__when__gte=timezone.now().date()-datetime.timedelta(days=30)).annotate(date=TruncDay('created__when')).values("date").annotate(count=Count('id')).order_by("date"), days=30)

    request_sparks = util.make_spark(tmodels.TatlRequest.objects.filter(timestamp__gte=timezone.now().date()-datetime.timedelta(days=30)).annotate(date=TruncDay('timestamp')).values("route", "date").annotate(count=Count('id')).order_by("date"), days=30, many="route")

    pags_by_site = models.PublishedArtifactGroup.objects.filter(is_latest=True, is_suppressed=False).values(site=F('owner__profile__institute__name')).annotate(count=Count('pk'), public=Count('pk', filter=Q(is_public=True)), private=Count('pk', filter=Q(is_public=False))).order_by('-count')
    good_pags = models.PAGQualityReportEquivalenceGroup.objects.filter(test_group__slug="cog-uk-elan-minimal-qc", is_pass=True, pag__is_latest=True, pag__is_suppressed=False)
    qc_by_site = {x['site']: x for x in good_pags.values(site=F('pag__owner__profile__institute__name')).annotate(is_pass=Count('site'))}
    for site_i, site in enumerate(pags_by_site):
        if site['site'] in qc_by_site:
            pags_by_site[site_i].update(qc_by_site[site['site']])
    total_pags = good_pags.count()

    return render(request, 'public/special/dashboard.html', {
        "total_collections": total_collections,
        "total_sequences": total_pags,
        "site_pags": pags_by_site,
        "adm2": [],
        "n_regions": len(adm2),

        "authors": models.Institute.objects.filter(gisaid_list__isnull=False).values("name", "code", "gisaid_lab_name", "gisaid_list").order_by("code"),

        "consensus_spark": consensus_spark,
        "request_sparks": request_sparks,
    })
