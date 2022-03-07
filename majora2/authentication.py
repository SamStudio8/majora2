from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions, permissions
from tatl.models import TatlRequest, TatlPermFlex

from django.utils import timezone

from majora2 import models
import json
import uuid

class TaskOwnerReadPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user == obj.user

class DataviewReadPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        mdv_code = request.query_params.get("mdv")
        if not mdv_code:
            return False
        else:
            try:
                mdv = models.MajoraDataview.objects.get(code_name=mdv_code)
            except models.MajoraDataview.DoesNotExist:
                return False

        p = models.MajoraDataviewUserPermission.objects.filter(
                profile__user=request.user,
                dataview__code_name=mdv_code,
                is_revoked=False,
                validity_start__lt=timezone.now(),
                validity_end__gt=timezone.now()
        ).first()
        if p:
            tflex = TatlPermFlex(
                user = request.user,
                substitute_user = None,
                used_permission = "majora2.v3.DataviewReadPermission",
                timestamp = timezone.now(),
                request=request.treq,
                content_object=mdv,
                #extra_context = json.dumps({
                #}),
            )
            tflex.save()
            return True
        return False #TODO logthis

