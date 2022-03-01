import sys
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2.models import Profile, Institute
from tatl import models as tmodels

from django.contrib.auth.models import User
from django.http.request import HttpRequest
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings

class Command(BaseCommand):
    help = "Move a user to another organisation"
    def add_arguments(self, parser):
        parser.add_argument('username', help="Username of user to be moved")
        parser.add_argument('site', help="Code of site to move the user to")

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)

        try:
            profile = Profile.objects.get(user__username=options["username"])
        except Profile.DoesNotExist:
            sys.stderr.write("No user with that username\n")
            sys.exit(1)

        try:
            institute = Institute.objects.get(code=options["site"])
        except Institute.DoesNotExist:
            sys.stderr.write("No site with that code\n")
            sys.exit(1)

        if institute != profile.institute:
            profile.institute = institute
            print("Moved %s to %s" % (profile.user.username, institute.code))
        else:
            print("%s is already in %s?!" % (profile.user.username, institute.code))
            sys.exit(2)

        # Flex perm
        treq = tmodels.TatlPermFlex(
            user = su,
            substitute_user = None,
            used_permission = "tatl.management.commands.usermv",
            timestamp = timezone.now(),
            content_object = profile,
            extra_context = json.dumps({
            }),
        )
        treq.save()

        # Flex verb
        tmodels.TatlVerb(request=None, verb="UPDATE", content_object=user,
            extra_context = json.dumps({
                "site": institute.code
            }),
        ).save()
