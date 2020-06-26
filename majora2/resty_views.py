from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from rest_framework.settings import api_settings
from rest_framework import status
from rest_framework.response import Response
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

        # Try ID as UUID, else assume its a "dice_name" (majora internal name)
        filter_on = "pk"
        if type(self.kwargs["pk"]) != uuid.UUID:
            try:
                # Check if this parameter looks like a UUID anyway
                uuid.UUID(self.kwargs["pk"], version=4)
            except ValueError:
                filter_on = "dice_name"

        filter[filter_on] = self.kwargs["pk"]
        obj = get_object_or_404(queryset, **filter) # Lookup the object
        self.check_object_permissions(self.request, obj)
        return obj

class ArtifactDetail(MajoraUUID4orDiceNameLookupMixin, generics.RetrieveAPIView):
    queryset = models.MajoraArtifact.objects.all()
    serializer_class = serializers.RestyArtifactSerializer

class BiosampleView(
                    MajoraUUID4orDiceNameLookupMixin,
                    mixins.CreateModelMixin,
                    mixins.UpdateModelMixin,
                    mixins.ListModelMixin,
                    mixins.RetrieveModelMixin,
                    viewsets.GenericViewSet):
    queryset = models.BiosampleArtifact.objects.all()
    serializer_class = serializers.RestyBiosampleArtifactSerializer
    #TODO permissions class

class PublishedArtifactGroupView(viewsets.ReadOnlyModelViewSet):
    queryset = models.PublishedArtifactGroup.objects.all()
    serializer_class = serializers.RestyPublishedArtifactGroupSerializer
