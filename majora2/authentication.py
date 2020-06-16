from rest_framework.authentication import TokenAuthentication
from rest_framework import exceptions

from django.utils import timezone

from majora2 import models

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
