from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.db.models import Count, F, Q, Avg
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator

from django.utils import timezone
from django.db.models.functions import TruncDay, Substr
import datetime

from . import models
from tatl import models as tmodels
from . import util
from . import public_util

import json

from django_datatables_view.base_datatable_view import BaseDatatableView

class OrderListJson(BaseDatatableView):
    model = models.PublishedArtifactGroup

    columns = ["id", "published_name", "published_date", "seqsite", "GISAID", "ENA", "qc_basic", "qc_high"]
    order_columns = ["id", "published_name", "published_date", "-", "-", "-", "-", "-"]
    max_display_length = 25

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
        elif column == "seqsite":
            try:
                return row.owner.profile.institute.code
            except:
                return "????"
        elif column == "qc_basic":
            try:
                return str(row.quality_groups.get(test_group__slug="cog-uk-elan-minimal-qc").is_pass)
            except:
                return ""
        elif column == "qc_high":
            try:
                return str(row.quality_groups.get(test_group__slug="cog-uk-high-quality-public").is_pass)
            except:
                return ""
        else:
            return super(OrderListJson, self).render_column(row, column)

    def filter_queryset(self, qs):
        search = self.request.GET.get('search[value]', None)
        if search:
            qs = qs.filter(published_name__icontains=search)

        default_seqsite = self.request.GET.get('default_seqsite', None)
        seqsite = self.request.GET.get('columns[3][search][value]', None)
        if seqsite:
            qs = qs.filter(owner__profile__institute__code=seqsite[1:-1])
        elif default_seqsite:
            qs = qs.filter(owner__profile__institute__code=default_seqsite)

        return qs

@cache_page(60 * 60)
def list_accessions(request):
    return render(request, 'public/special/pag_list.html', {
        "pag_ajax_url": reverse("api.datatable.pag.get"),
        "site_codes": sorted(models.Institute.objects.all().values_list('code', flat=True)),
    })


def view_facts(request):
    qs = models.MajoraFact.objects.filter(restricted=False).values("namespace", "key", "value_type", "value", "counter", "timestamp")
    qs_json = json.dumps(list(qs), default=str) # use default to co-erce ts
    return HttpResponse(qs_json, content_type="application/json")


@cache_page(60 * 90)
def render_architect(request):
    try:
        util.create_or_increment_fact(namespace="tatl", key="cached_architects")
    except:
        pass
    return HttpResponse('<img src="data:image/png;base64,%s" />' % public_util.select_egg())
