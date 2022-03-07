from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone


from celery.signals import after_task_publish,task_success,task_prerun,task_postrun
from django_slack import slack_message

import json
import logging

from . import models
from majora2.models import Profile

from oauth2_provider.signals import app_authorized

logger = logging.getLogger('majora')

@receiver(post_save, sender=models.TatlVerb)
def syslog_verb(sender, instance, **kwargs):
    # Emit syslog
    if instance.request:
        req_uuid = instance.request.response_uuid if instance.request else ""
        req_user = "anonymous"
        remote_addr = instance.request.remote_addr
        ts = str(instance.request.timestamp)
        is_api = instance.request.is_api
        if hasattr(instance.request, "user"):
            if instance.request.user:
                req_user = instance.request.user.username
    else:
        req_uuid = "NONE"
        req_user = "NONE"
        remote_addr = "NONE"
        ts = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        is_api = False

    logger.info("[VERB] request=%s user=%s verb=%s object_model=%s object_uuid=%s addr=%s at=%s api=%d" % (
        req_uuid,
        req_user,
        instance.verb,
        instance.content_object._meta.model.__name__,
        instance.content_object.id,
        remote_addr,
        ts.replace(" ", "_"),
        1 if is_api else 0,
    ))

@receiver(post_save, sender=models.TatlPermFlex)
def announce_perm_flex(sender, instance, **kwargs):
    if settings.SLACK_CHANNEL_TATL:
        ext = ''
        if instance.extra_context:
            try:
                ext = "\n```%s```" % json.dumps(json.loads(instance.extra_context), indent=4, sort_keys=True)
            except Exception as e:
                pass

        try:
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
        except:
            pass

@receiver(app_authorized)
def handle_app_authorized(sender, request, token, **kwargs):
    if token.user:
        request.treq.user = token.user
        request.treq.save()
    models.TatlVerb(request=request.treq, verb="OAUTHORIZE", content_object=token.application).save()

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
def task_postrun_tatl(signal=None, sender=None, task_id=None, task=None, args=None, retval=None, state=None, **kwargs):
    ttask = models.TatlTask.objects.get(celery_uuid=task_id)
    now = timezone.now()
    ttask.response_time = now - ttask.timestamp
    ttask.state = state
    ttask.save()

@task_postrun.connect()
def task_postrun_slack(signal=None, sender=None, task_id=None, task=None, args=None, retval=None, state=None, **kwargs):
    if settings.SLACK_CHANNEL:
        ttask = models.TatlTask.objects.get(celery_uuid=task_id)
        slack_message('slack/blank', {
        }, [{
            "mrkdwn_in": ["text", "pretext", "fields"],
            "title": "Task ended",
            "title_link": "",
            "text": "Task %s (`%s`) for `%s` finished with state *%s*" % (task.name, task_id, ttask.user.username if ttask.user else 'unknown', state),
            "footer": "Task end spotted by Majora",
            "footer_icon": "https://avatars.slack-edge.com/2019-05-03/627972616934_a621b7d3a28c2b6a7bd1_512.jpg",
            "ts": int(timezone.now().timestamp()),
        }])
