from django.contrib.auth.decorators import login_required

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework import permissions

from two_factor.views.mixins import OTPRequiredMixin

from majora2 import models
from majora2 import resty_serializers as serializers
from majora2.authentication import TatlTokenAuthentication

class ArtifactDetail(generics.RetrieveAPIView):
    authentication_classes = [TatlTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    queryset = models.MajoraArtifact.objects.all()
    serializer_class = serializers.RestyArtifactSerializer

