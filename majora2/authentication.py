from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions, permissions
from tatl.models import TatlRequest, TatlPermFlex

from django.utils import timezone

from majora2 import models
import json
import uuid

class TatlTokenAuthentication(TokenAuthentication):
    model = models.ProfileAPIKey

    def authenticate_credentials(self, head_token):
        try:
            username, token = head_token.split('|', 1)
        except ValueError:
            raise exceptions.AuthenticationFailed('Bad user or token.')

        try:
            key = models.ProfileAPIKey.objects.get(key=token, profile__user__username=username, was_revoked=False, validity_start__lt=timezone.now(), validity_end__gt=timezone.now())
        except models.ProfileAPIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed('Bad user or token.')

        return (key.profile.user, key)

class APIKeyPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        user = request.user
        key = request.auth

        if not key:
            return False

        #TODO We can build more complex permissions here with lists of lists
        permission = view.majora_api_permission

        if permission:
            # Check permission has been granted to user
            if not user.has_perm(permission):
                return False

            # Check permission has been granted to key
            if not key.key_definition.permission:
                return False
            if key.key_definition.permission.codename != permission.split('.')[1]:
                return False

        treq = TatlRequest.objects.get(response_uuid=view.response_uuid)
        treq.user = user
        treq.save()

        if permission:
            tflex = TatlPermFlex(
                user = user,
                substitute_user = None,
                used_permission = permission,
                timestamp = timezone.now(),
                request=treq,
                content_object = treq, #TODO just use the request for now
                #extra_context = json.dumps({
                #}),
            )
            tflex.save()
        # TODO Add an extra permflex in has_object_permission
        return True

