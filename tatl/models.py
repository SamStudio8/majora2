from django.db import models
from django.conf import settings

# Create your models here.
class TatlRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="requests")
    route = models.CharField(max_length=128)
    payload = models.TextField()
    timestamp = models.DateTimeField()

