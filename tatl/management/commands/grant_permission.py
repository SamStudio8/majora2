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
            user = User.objects.get(username=options["user"])
        except:
            print("No user with that username.")
            sys.exit(1)

        valid_permissions = []
        for p in options["permission"].split("&"):
            p = p.split('.')[-1]
            try:
                permission = Permission.objects.get(codename=p)
            except:
                print("No permission with name %s" % p)
                continue

            valid_permissions.append(permission.codename)
            user.user_permissions.add(permission)

        if len(valid_permissions) > 0:
            user.save()
            treq = models.TatlPermFlex(
                user = su,
                substitute_user = None,
                used_permission = "tatl.management.commands.grant_permission",
                timestamp = timezone.now(),
                content_object = user,
                extra_context = json.dumps({ "permissions": valid_permissions }),
            )
            treq.save()
