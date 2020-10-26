from django_datatables_view.base_datatable_view import BaseDatatableView
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden

from . import models


class BiosampleOrderListJson(BaseDatatableView):
    model = models.BiosampleArtifact

    columns = ["id", "central_sample_id", "sample_source", "collected_at", "collected_by", "type", "collection_date"]
    order_columns = ["id", "central_sample_id", "-", "-", "-", "-", "-"]
    max_display_length = 25

    def render_column(self, row, column):
        if column == "sample_source":

            if row.primary_group:
                source = str(row.primary_group)
            else:
                source = "Unlinked"

            if row.created:
                source_def = "(%s%s)" % (row.created.source_age if row.created.source_age else "?", row.created.source_sex)
            else:
                source_def = "(?)"

            return "%s %s" % (source, source_def)

        elif column == "collected_at":
            adm1 = "?"
            adm2 = "?"
            if row.created:
                adm1 = row.created.collection_location_adm1
                adm2 = row.created.collection_location_adm2
            return "%s / %s" % (adm1, adm2)

        elif column == "collected_by":
            collector = "?"
            if row.created:
                collector = row.created.collected_by
            return collector

        elif column == "type":

            sample_type = row.sample_type_collected
            if row.sample_site:
                sample_type = "%s (%s)" % (sample_type, row.sample_site)
            return sample_type

        elif column == "collection_date":
            if row.created:
                return row.created.collection_date
            else:
                return "?"
        else:
            return super(BiosampleOrderListJson, self).render_column(row, column)

    def filter_queryset(self, qs):
        # Restrict to current user
        if not self.request.user:
            raise HttpResponseForbidden()

        qs = qs.filter(created__who__profile__institute__code=self.request.user.profile.institute.code)

        search = self.request.GET.get('search[value]', None)
        if search:
            qs = qs.filter(central_sample_id__icontains=search)
        return qs
