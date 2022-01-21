from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q

from . import models

import json
import datetime
import dateutil.parser
from django.contrib.auth.models import User

from django.contrib.auth.decorators import login_required

@login_required
def list_dataviews(request):
    return render(request, 'private/special/dataview_list.html', {
        "dataviews": models.MajoraDataview.objects.all(),
    })
