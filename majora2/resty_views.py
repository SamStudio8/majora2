from django.contrib.auth.decorators import login_required

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from majora2 import models
from majora2 import resty_serializers as serializers

@login_required
@api_view(['GET', 'POST'])
def artifact_detail(request, pk, format=None):
    try:
        artifact = models.MajoraArtifact.objects.get(pk=pk)
    except models.MajoraArtifact.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        serializer = artifact.get_resty_serializer()(artifact)
        return Response(serializer.data)
    elif request.method == "POST":
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
