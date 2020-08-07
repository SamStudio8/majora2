from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from celery.signals import after_task_publish,task_success,task_prerun,task_postrun
from django_slack import slack_message

import json

from . import models
from majora2.models import Profile

@receiver(post_save, sender=models.TatlPermFlex)
def announce_perm_flex(sender, instance, **kwargs):
    if settings.SLACK_CHANNEL_TATL:
        ext = ''
        if instance.extra_context:
            try:
                ext = "\n```%s```" % json.dumps(json.loads(instance.extra_context), indent=4, sort_keys=True)
            except Exception as e:
                pass

        slack_message('slack/permflex', {
            "channel": settings.SLACK_CHANNEL_TATL,
        }, [{
            "text": "User `%s` flexed their `%s` permission on `%s` at %s %s" % (
                instance.user,
                instance.used_permission,
                str(instance.content_object),
                str(instance.timestamp),
                ext,
            ),
        }])

@task_prerun.connect()
def task_prerun(signal=None, sender=None, task_id=None, task=None, args=None, **kwargs):
    kwargs = kwargs.get("kwargs") # Don't ask

    treq = None
    if kwargs.get("response_uuid"):
        treq = models.TatlRequest.objects.get(response_uuid=kwargs.get("response_uuid"))

    tuser = None
    if kwargs.get("user"):
        tuser = Profile.objects.get(user__pk=kwargs.get("user"))
        tuser = tuser.user

    ttask = models.TatlTask(
        celery_uuid = task_id,
        task = task.name,
        payload = json.dumps(kwargs),
        timestamp = timezone.now(),
        request = treq,
        user = tuser,
    )
    ttask.save()

@task_postrun.connect()
def task_postrun(signal=None, sender=None, task_id=None, task=None, args=None, retval=None, state=None, **kwargs):
    ttask = models.TatlTask.objects.get(celery_uuid=task_id)
    now = timezone.now()
    ttask.response_time = now - ttask.timestamp
    ttask.state = state
    ttask.save()
