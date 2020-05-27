from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from . import models

from django_slack import slack_message
from django.core.mail import send_mail
import json

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
