import sys
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2.models import Profile
from tatl import models as tmodels

from django.contrib.auth.models import User
from django.http.request import HttpRequest
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings

class Command(BaseCommand):
    help = "Forcibly approve a new user"
    def add_arguments(self, parser):
        parser.add_argument('username', help="Username of user to be approved")

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)

        try:
            profile = Profile.objects.get(user__username=options["username"])
        except Profile.DoesNotExist:
            sys.stderr.write("No user with that username\n")
            sys.exit(1)

        user = profile.user

        if user.is_active and profile.is_site_approved:
            sys.stderr.write("User already approved\n")
            sys.exit(0)

        # Approve
        profile.is_site_approved = True # force local site approval
        profile.save()

        user.is_active = True # sysadmin override
        user.save()

        sys.stderr.write("%s approved!\n" % user.username)

        # Flex perm
        treq = tmodels.TatlPermFlex(
            user = su,
            substitute_user = None,
            used_permission = "tatl.management.commands.userapprove",
            timestamp = timezone.now(),
            content_object = user,
            extra_context = json.dumps({
            }),
        )
        treq.save()

        # Flex verb
        tmodels.TatlVerb(request=None, verb="UPDATE", content_object=user,
            extra_context = json.dumps({
            }),
        ).save()
