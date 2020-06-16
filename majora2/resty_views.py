from django.contrib.auth.decorators import login_required

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from two_factor.views.mixins import OTPRequiredMixin

from majora2 import models
from majora2 import resty_serializers as serializers

class ArtifactDetail(OTPRequiredMixin, APIView):

    def get_object(self, pk):
        try:
            return models.MajoraArtifact.objects.get(pk=pk)
        except models.MajoraArtifact.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def get(self, request, pk, format=None):
        artifact = self.get_object(pk)
        serializer = artifact.get_resty_serializer()(artifact)
        return Response(serializer.data)

