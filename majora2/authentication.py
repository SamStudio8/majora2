from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions, permissions
from tatl.models import TatlRequest, TatlPermFlex

from django.utils import timezone

from majora2 import models
import json

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

        # https://stackoverflow.com/questions/4581789/how-do-i-get-user-ip-address-in-django
        remote_addr = None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            remote_addr = x_forwarded_for.split(',')[0]
        else:
            remote_addr = request.META.get('REMOTE_ADDR')

        # Not really sure if this is the right venue for this shit
        json_data = json.dumps(request.data)
        treq = TatlRequest(
            user = None,
            substitute_user = None,
            route = request.path,
            payload = json_data,
            timestamp = timezone.now(),
            remote_addr = remote_addr,
        )
        treq.save()
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

