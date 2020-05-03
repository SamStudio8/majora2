import time

from django.dispatch import receiver
from django.conf import settings

from . import signals

from django_slack import slack_message
from django.core.mail import send_mail

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
            "text": "Sample %s uploaded from %s" % (sample_id, submitter),
            #"footer": "New sample spotted by Majora",
            #"footer_icon": "https://avatars.slack-edge.com/2019-05-03/627972616934_a621b7d3a28c2b6a7bd1_512.jpg",
            #"ts": int(time.time()),
        }])

@receiver(signals.activated_registration)
def recv_activated_registration(sender, username, email, **kwargs):
    send_mail(
        '[majora@climb] Your access request has been approved',
        '''You're receiving this email because you requested a %s account. Your request has been approved.
        Your username is %s

        Please find guidance on using our systems and providing data via: https://docs.covid19.climb.ac.uk/.
        ''' % (settings.INSTANCE_NAME, username),
        None,
        [email],
        fail_silently=False,
    )


@receiver(signals.task_end)
def recv_task_end(sender, task, task_id, **kwargs):
    if settings.SLACK_CHANNEL:
        slack_message('slack/blank', {
        }, [{
            "mrkdwn_in": ["text", "pretext", "fields"],
            "title": "Task ended",
            "title_link": "",
            "text": "Task %s (%s) appears to have finished" % (task, task_id),
            "footer": "Task end spotted by Majora",
            "footer_icon": "https://avatars.slack-edge.com/2019-05-03/627972616934_a621b7d3a28c2b6a7bd1_512.jpg",
            "ts": int(time.time()),
        }])
