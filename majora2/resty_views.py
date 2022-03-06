from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.apps import apps

from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework import viewsets
from rest_framework import mixins
from rest_framework import permissions
from rest_framework.status import HTTP_400_BAD_REQUEST
from rest_condition import Or

from majora2 import tasks
from majora2 import models
from majora2 import resty_serializers as serializers
from majora2.authentication import TatlTokenAuthentication, APIKeyPermission, TaskOwnerReadPermission, DataviewReadPermission
from tatl.models import TatlRequest, TatlPermFlex

from oauth2_provider.contrib.rest_framework import TokenHasReadWriteScope, TokenHasScope

import uuid
import json

class RequiredParamRetrieveMixin(object):

    def _check_param(self, request):
        # Check the view has the required params (if any)
        for param in self.majora_required_params:
            if param not in request.query_params:
                return Response({"detail": "Your request is missing a required parameter: %s" % param}, HTTP_400_BAD_REQUEST)

    def retrieve(self, request, *args, **kwargs):
        bad = self._check_param(request)
        if bad:
            return bad
        return super().retrieve(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        bad = self._check_param(request)
        if bad:
            return bad
        return super().list(request, *args, **kwargs)

class MajoraCeleryListingMixin(object):
    def list(self, request, *args, **kwargs):
        queryset = list(self.filter_queryset(self.get_queryset()).values_list('id', flat=True))

        api_o = {}

        if self.celery_task:
            context = {}
            for param in self.majora_required_params:
                context[param] = request.query_params[param]
            celery_task = self.celery_task.delay(queryset, context=context, user=request.user.pk, response_uuid=request.treq.response_uuid)
            if celery_task:
                api_o["response_uuid"] = request.treq.response_uuid
                api_o["errors"] = 0
                api_o["params"] = request.query_params
                api_o["expected_n"] = len(queryset)
                api_o["tasks"] = [celery_task.id]
                api_o["messages"] = ["This is an experimental API and can change at any time.", "Call api.majora.task.get with the appropriate task ID later...", "`expected_n` value will be incorrect for FAST views"]
            else:
                api_o["errors"] = 1
                api_o["messages"] = "Could not add requested task to Celery..."
            return Response(
                api_o
            )


#TODO How to handle errors properly here? Just let them 500 for now
class RestyDataview(
                    RequiredParamRetrieveMixin,
                    MajoraCeleryListingMixin,
                    viewsets.GenericViewSet):

    #NOTE Although DataviewReadPermission implies APIKeyPermission, the latter
    # actually checks the API Key being used is suitable for the permission requested
    # so we need to check both here
    permission_classes = [permissions.IsAuthenticated & DataviewReadPermission & TokenHasScope]
    majora_api_permission = "majora2.can_read_dataview_via_api" #TODO Integrate with model
    required_scopes = ['majora2.can_read_dataview_via_api']

    celery_task = tasks.task_get_mdv_v3
    majora_required_params = ["mdv"]

    def get_serializer_class(self):
        mdv_code = self.request.query_params.get("mdv")
        mdv = models.MajoraDataview.objects.get(code_name=mdv_code)
        return apps.get_model("majora2", mdv.entry_point).get_resty_serializer()

    def get_queryset(self):
        mdv_code = self.request.query_params.get("mdv")
        mdv = models.MajoraDataview.objects.get(code_name=mdv_code)
        queryset = apps.get_model("majora2", mdv.entry_point).objects.all()

        return queryset.filter( mdv.get_filters() )

