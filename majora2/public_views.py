from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.db.models import Count

from . import models
def sample_sequence_count_dashboard(request):
    collections = models.BiosourceSamplingProcess.objects.values("collected_by").annotate(Count("collected_by")).order_by("-collected_by__count")
    total_collections = models.BiosourceSamplingProcess.objects.count()

    return render(request, 'public/special/dashboard.html', {
        "collections": collections,
        "total_collections": total_collections,
        "sequences": [],
        "total_sequences": 0,
    })
