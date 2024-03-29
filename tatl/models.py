import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from oauth2_provider.models import AbstractApplication

from majora2.util import create_or_increment_fact

class TatlRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="requests")
    substitute_user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="su_requests")
    remote_addr = models.CharField(max_length=48, blank=True, null=True)

    view_path = models.CharField(max_length=128)
    view_name = models.CharField(max_length=128)

    params = models.TextField(default="{}")
    payload = models.TextField(default="{}")

    timestamp = models.DateTimeField()
    response_time = models.DurationField(blank=True, null=True)

    status_code = models.PositiveSmallIntegerField()
    response_uuid = models.UUIDField(default=uuid.uuid4, blank=True, null=True, unique=True) #TODO I want this to be the UUID but its not trivial now

    is_api = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_api and self.status_code > 0:
            # Roughly catch a successful looking API request
            # The treq is saved a few times and the status_code is one of the last things that are changed
            try:
                create_or_increment_fact(namespace="tatl", key="api_requests")
            except:
                pass
        super().save(*args, **kwargs)


class TatlTask(models.Model):
    celery_uuid = models.UUIDField(unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="tasks")
    substitute_user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="su_tasks")

    task = models.CharField(max_length=128)
    state = models.CharField(max_length=48, blank=True, null=True)
    payload = models.TextField()
    timestamp = models.DateTimeField()
    response_time = models.DurationField(blank=True, null=True)

    request = models.OneToOneField('TatlRequest', on_delete=models.PROTECT, related_name="task", blank=True, null=True)

class TatlVerb(models.Model):
    verb = models.CharField(max_length=10)

    #TODO Migrate this to non-generic and provide a link for Artifact, Group (Process?) to improve performance
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64, db_index=True) # ffs you really cooked this one (needs to support positive int and uuid)
    content_object = GenericForeignKey('content_type', 'object_id')

    extra_context = models.TextField(blank=True, null=True, default="{}")

    request = models.ForeignKey('TatlRequest', on_delete=models.PROTECT, related_name="verbs", blank=True, null=True)

    def __str__(self):
        return "%s: %s" % (self.verb, str(self.content_object))

class TatlPermFlex(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="actions")
    substitute_user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="su_actions")
    used_permission = models.CharField(max_length=64) # this could link directly to the permission model but i think the perm name will do

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64) # ffs you really cooked this one (needs to support positive int and uuid)
    content_object = GenericForeignKey('content_type', 'object_id')

    extra_context = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField()

    request = models.ForeignKey('TatlRequest', on_delete=models.PROTECT, related_name="action", blank=True, null=True)

class OAuth2CodeOnlyApplication(AbstractApplication):
    GRANT_AUTHORIZATION_CODE = "authorization-code"
    GRANT_TYPES = (
        (GRANT_AUTHORIZATION_CODE, _("Authorization code")),
    )

    authorization_grant_type = models.CharField(
        max_length=32, choices=GRANT_TYPES
    )

from . import receivers
