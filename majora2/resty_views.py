from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from rest_framework.settings import api_settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework import permissions
from rest_framework import viewsets
from rest_framework import mixins

from two_factor.views.mixins import OTPRequiredMixin

from majora2 import models
from majora2 import resty_serializers as serializers
from majora2.authentication import TatlTokenAuthentication

import uuid

class MajoraUUID4orDiceNameLookupMixin(object):
    def get_object(self):
        queryset = self.get_queryset()             # Get the base queryset
        queryset = self.filter_queryset(queryset)  # Apply any filter backends
        filter = {}

        filter_on = "pk"
        if self.majora_alternative_field:
            # Try ID as UUID, else assume its a "dice_name" (majora internal name)
            if type(self.kwargs["pk"]) != uuid.UUID:
                try:
                    # Check if this parameter looks like a UUID anyway
                    uuid.UUID(self.kwargs["pk"], version=4)
                except ValueError:
                    filter_on = self.majora_alternative_field

        filter[filter_on] = self.kwargs["pk"]
        obj = get_object_or_404(queryset, **filter) # Lookup the object
        self.check_object_permissions(self.request, obj)
        return obj

class ArtifactDetail(MajoraUUID4orDiceNameLookupMixin, generics.RetrieveAPIView):
    queryset = models.MajoraArtifact.objects.all()
    serializer_class = serializers.RestyArtifactSerializer
    majora_alternative_field = "dice_name"

class BiosampleView(
                    MajoraUUID4orDiceNameLookupMixin,
                    mixins.ListModelMixin,
                    mixins.RetrieveModelMixin,
                    viewsets.GenericViewSet):
    queryset = models.BiosampleArtifact.objects.all()
    serializer_class = serializers.RestyBiosampleArtifactSerializer
    majora_alternative_field = "dice_name"
    #TODO permissions class


class TaskView(APIView):
    renderer_classes = [JSONRenderer]
    def get(self, request, tid, format=None):
        task_id = tid
        if not task_id:
            return Response({"booooooooooooo": 1})

        api_o = {}
        from mylims.celery import app
        res = app.AsyncResult(task_id)
        if res.state == "SUCCESS":
            try:
                api_o.update(res.get())
            except Exception as e:
                api_o["errors"] = 1
                api_o["messages"] = str(e)
        else:
            api_o["warnings"] = 1
            api_o["messages"] = "Task is not (yet) SUCCESS..."

        api_o["task"] = {
            "id": task_id,
            "state": res.state,
        }
        return Response(api_o)


class PublishedArtifactGroupView(
                    MajoraUUID4orDiceNameLookupMixin,
                    mixins.ListModelMixin,
                    mixins.RetrieveModelMixin,
                    viewsets.GenericViewSet):
    serializer_class = serializers.RestyPublishedArtifactGroupSerializer
    majora_alternative_field = "published_name"
    queryset = models.PublishedArtifactGroup.objects.all()

    def get_queryset(self):
        queryset = self.queryset

        service = self.request.query_params.get('service', None)
        public = self.request.query_params.get('public', None)
        private = self.request.query_params.get('private', None)

        if public and private:
            # Ignore
            pass
        elif public:
            if service:
                queryset = queryset.filter(accessions__service=service)
            else:
                queryset = queryset.filter(is_public=True)
        elif private:
            if service:
                queryset = queryset.filter(~Q(accessions__service=service))
            else:
                queryset = queryset.filter(is_public=False)
        return queryset

    def list(self, request, *args, **kwargs):
        #TODO This overrides the list function entirely which loses pagination
        # there is probably a "correct" way to do this re:mixins
        queryset = list(self.filter_queryset(self.get_queryset()).values_list('id', flat=True))

        api_o = {}
        from . import tasks
        celery_task = tasks.task_get_pag_by_qc_v3.delay(queryset, context={"leaf_cls":request.query_params.get("leaf_cls")})
        if celery_task:
            api_o["errors"] = 0
            api_o["test"] = request.query_params
            api_o["expected_n"] = len(queryset)
            api_o["tasks"] = celery_task.id
            api_o["messages"] = "Call api.majora.task.get with the appropriate task ID later..."
        else:
            api_o["errors"] = 1
            api_o["messages"] = "Could not add requested task to Celery..."
        return Response(
            api_o
        )
