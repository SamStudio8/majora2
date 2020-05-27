from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2 import models
from django.contrib.auth.models import User, Permission

from tatl import models

import sys
import json

class Command(BaseCommand):
    help = "Grant a permission to a user"
    def add_arguments(self, parser):
        parser.add_argument('permission')
        parser.add_argument('user')

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)
        try:
            permission = Permission.objects.get(codename=options["permission"])
        except:
            print("No permission with that name.")
            sys.exit(1)

        try:
            user = User.objects.get(username=options["user"])
        except:
            print("No user with that username.")
            sys.exit(1)

        user.user_permissions.add(permission)
        user.save()
        treq = models.TatlPermFlex(
            user = su,
            substitute_user = None,
            used_permission = "tatl.management.commands.grant_permission",
            timestamp = timezone.now(),
            content_object = user,
            extra_context = json.dumps({ "permission": permission.codename }),
        )
        treq.save()
