import time

from django.dispatch import receiver
from django.conf import settings

from . import signals

from django_slack import slack_message

@receiver(signals.new_registration)
def recv_new_registration(sender, username, first_name, last_name, organisation, **kwargs):
    if settings.SLACK_CHANNEL:
        slack_message('slack/blank', {
        }, [{
            "mrkdwn_in": ["text", "pretext", "fields"],
            "title": "New user registration",
            "title_link": "",
            "text": "%s %s (%s) requested account %s to be approved" % (first_name, last_name, organisation, username),
            "footer": "New user spotted by Majora",
            "footer_icon": "https://avatars.slack-edge.com/2019-05-03/627972616934_a621b7d3a28c2b6a7bd1_512.jpg",

            "fields": [
                {
                    "title": "Metadata",
                    "short": False
                },
                {
                    "title": "User",
                    "short": True
                },
                {
                    "value": username,
                    "short": True
                },
                {
                    "title": "Name",
                    "short": True
                },
                {
                    "value": "%s %s" % (first_name, last_name),
                    "short": True
                },
                {
                    "title": "Organisation",
                    "short": True
                },
                {
                    "value": organisation,
                    "short": True
                },
            ],
            "ts": int(time.time()),
        }])

@receiver(signals.new_sample)
def recv_new_sample(sender, sample_id, submitter, **kwargs):
    if settings.SLACK_CHANNEL:
        slack_message('slack/blank', {
        }, [{
            "mrkdwn_in": ["text", "pretext", "fields"],
            "title": "New sample",
            "title_link": "",
            "text": "%s has provided sample metadata for sample %s" % (submitter, sample_id),
            "footer": "New sample spotted by Majora",
            "footer_icon": "https://avatars.slack-edge.com/2019-05-03/627972616934_a621b7d3a28c2b6a7bd1_512.jpg",

            "fields": [
                {
                    "title": "Metadata",
                    "short": False
                },
                {
                    "title": "Sample",
                    "short": True
                },
                {
                    "value": sample_id,
                    "short": True
                },
                {
                    "title": "Organisation",
                    "short": True
                },
                {
                    "value": submitter,
                    "short": True
                },
            ],
            "ts": int(time.time()),
        }])
