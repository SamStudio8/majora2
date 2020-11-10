import time

from django.dispatch import receiver
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from . import models
from . import signals

from django_slack import slack_message
from django.core.mail import send_mail

@receiver(signals.revoked_profile)
def email_revoked_profile(sender, username, organisation, email, reason, **kwargs):
    send_mail(
        '[majora@climb] Your account has been closed',
        '''You're receiving this email because your %s account (username %s) has been closed.

        As a result of this:
        * You will no longer be able to use your Majora account to access data.
        * You will be unable to access CLIMB systems with SSH or upload files with rsync.
        * Any API requests you send will now be rejected.

        If you do not believe this should have happened, please contact %s as soon as possible. Do not contact the CLIMB team or #account-requests with requests to be reactivated.
        ''' % (settings.INSTANCE_NAME, username, "the accounts team (%s)" % settings.MAJORA_ACCOUNT_MAIL if hasattr(settings, "MAJORA_ACCOUNT_MAIL") and len(settings.MAJORA_ACCOUNT_MAIL) > 0 else "your site lead"),
        None,
        [email],
        fail_silently=True,
    )
    if settings.SLACK_CHANNEL:
        slack_message('slack/blank', {
        }, [{
            "mrkdwn_in": ["text", "pretext", "fields"],
            "title": "User profile revoked",
            "title_link": "",
            "text": "Access for %s has been revoked" % (username),
            "footer": "Revocation spotted by Majora",
            "footer_icon": "https://avatars.slack-edge.com/2019-05-03/627972616934_a621b7d3a28c2b6a7bd1_512.jpg",

            "fields": [
                {
                    "title": "Metadata",
                    "short": False
                },
                {
                    "title": "Email",
                    "short": True
                },
                {
                    "value": email,
                    "short": True
                },
                {
                    "title": "Org Code",
                    "short": True
                },
                {
                    "value": organisation,
                    "short": True
                },
                {
                    "title": "Reason",
                    "short": True
                },
                {
                    "value": reason,
                    "short": True
                },
            ],
            "ts": int(time.time()),
        }])

@receiver(signals.new_registration)
def recv_new_registration(sender, username, first_name, last_name, organisation, email, **kwargs):
    from django.contrib.auth.models import User, Permission
    perm = Permission.objects.get(codename='can_approve_profiles')
    site_admins = models.Profile.objects.filter(user__user_permissions=perm, institute__name=organisation) # TODO works for users specifically given this perm
    send_mail(
        '[majora@climb] A user has requested access to Majora for your organisation',
        '''You're receiving this email because %s %s has requested a %s account and you are responsible for approving accounts for your organisation.
        Please verify the user and if the request is valid, approve the request from Majora: %s
        ''' % (first_name, last_name, settings.INSTANCE_NAME, reverse('list_site_profiles')),
        None,
        [p.user.email for p in site_admins],
        fail_silently=True,
    )
    if settings.SLACK_CHANNEL:
        slack_message('slack/blank', {
        }, [{
            "mrkdwn_in": ["text", "pretext", "fields"],
            "title": "New user registration WAITING for approval by site",
            "title_link": "",
            "text": "%s %s (%s) requested account %s to be added" % (first_name, last_name, organisation, username),
            "footer": "New user spotted by Majora",
            "footer_icon": "https://avatars.slack-edge.com/2019-05-03/627972616934_a621b7d3a28c2b6a7bd1_512.jpg",

            "fields": [
                {
                    "title": "Metadata",
                    "short": False
                },
                {
                    "title": "Email",
                    "short": True
                },
                {
                    "value": email,
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
                {
                    "title": "Approvers",
                    "short": True
                },
                {
                    "value": str(["%s %s" % (x.user.first_name, x.user.last_name) for x in site_admins]),
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

@receiver(signals.site_approved_registration)
def recv_site_approval(sender, approver, approved_profile, **kwargs):
    from tatl.models import TatlPermFlex
    treq = TatlPermFlex(
        user = sender.user,
        substitute_user = None,
        used_permission = "can_approve_profiles",
        timestamp = timezone.now(),
        content_object = approved_profile,
    )
    treq.save()
    if settings.SLACK_CHANNEL:
        slack_message('slack/blank', {
        }, [{
            "mrkdwn_in": ["text", "pretext", "fields"],
            "title": "New user registration approved by site",
            "title_link": "",
            "text": "%s %s (%s) requested account %s to be added" % (approved_profile.user.first_name, approved_profile.user.last_name, approved_profile.institute.name, approved_profile.user.username),
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
                    "value": approved_profile.user.username,
                    "short": True
                },
                {
                    "title": "Name",
                    "short": True
                },
                {
                    "value": "%s %s" % (approved_profile.user.first_name, approved_profile.user.last_name),
                    "short": True
                },
                {
                    "title": "Email",
                    "short": True
                },
                {
                    "value": approved_profile.user.email,
                    "short": True
                },
                {
                    "title": "Organisation",
                    "short": True
                },
                {
                    "value": approved_profile.institute.name,
                    "short": True
                },
                {
                    "title": "Approver",
                    "short": True
                },
                {
                    "value": "%s %s" % (approver.first_name, approver.last_name),
                    "short": True
                },
            ],
            "ts": int(time.time()),
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


