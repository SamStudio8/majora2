from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from django.db import models
from django.conf import settings

# Create your models here.
class TatlRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="requests")
    substitute_user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="su_requests")
    route = models.CharField(max_length=128)
    payload = models.TextField()
    remote_addr = models.CharField(max_length=48, blank=True, null=True)
    timestamp = models.DateTimeField()

class TatlPermFlex(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="actions")
    substitute_user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="su_actions")
    used_permission = models.CharField(max_length=64) # this could link directly to the permission model but i think the perm name will do

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64) # ffs you really cooked this one (needs to support positive int and uuid)
    content_object = GenericForeignKey('content_type', 'object_id')

    extra_context = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField()

    request = models.OneToOneField('TatlRequest', on_delete=models.PROTECT, related_name="action", blank=True, null=True)
