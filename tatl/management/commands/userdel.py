from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from django.contrib.auth.models import User, Permission, Group

from tatl import models
from majora2 import signals

import sys
import json

class Command(BaseCommand):
    help = "Revoke a user account"
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--username')
        group.add_argument('--email')
        parser.add_argument('--reason', required=True)

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)

        try:
            if options.get("email"):
                user = User.objects.get(email=options["email"])
            elif options.get("username"):
                user = User.objects.get(username=options["username"])
            else:
                print("[WARN] idtype must be '--username' or '--email'")
                sys.exit(2)
        except:
            print("[FAIL] No user with that id.")
            sys.exit(1)

        ts = timezone.now()

        if user.profile.is_revoked:
            sys.stderr.write("[NOTE] User %s is already deactivated\n" % (user.username))
            sys.exit(3)

        # Disable the user
        user.is_active = False
        user.save()
        sys.stderr.write("[NOTE] User %s deactivated\n" % (user.username))

        # Set the revoke access flags
        user.profile.is_revoked = True
        user.profile.revoked_reason = options["reason"]
        user.profile.revoked_timestamp = ts
        user.profile.save()
        sys.stderr.write("[NOTE] User %s flagged as revoked\n" % (user.username))

        # Flex perm
        treq = models.TatlPermFlex(
            user = su,
            substitute_user = None,
            used_permission = "tatl.management.commands.userdel",
            timestamp = ts,
            content_object = user,
            extra_context = json.dumps({
                "is_revoked": True,
                "revoked_reason": options["reason"],
                "revoked_timestamp_ts": ts.timestamp(),
                "revoked_timestamp_str": ts.strftime("%Y-%m-%d %H:%M"),
            }),
        )
        treq.save()

        # Flex verb
        models.TatlVerb(request=None, verb="REVOKE", content_object=user,
            extra_context = json.dumps({
                "is_revoked": True,
                "revoked_reason": options["reason"],
                "revoked_timestamp_ts": ts.timestamp(),
                "revoked_timestamp_str": ts.strftime("%Y-%m-%d %H:%M"),
            }),
        ).save()
        signals.revoked_profile.send(sender=None, username=user.username, organisation=user.profile.institute.code, email=user.email, reason=options["reason"])
