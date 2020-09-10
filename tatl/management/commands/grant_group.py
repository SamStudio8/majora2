from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2 import models
from django.contrib.auth.models import User, Permission, Group

from tatl import models

import sys
import json

class Command(BaseCommand):
    help = "Grant a permission group to a user"
    def add_arguments(self, parser):
        parser.add_argument('user')
        parser.add_argument('group')

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)

        if options["user"] == '*':
            users = User.objects.all()
        else:
            try:
                users = [User.objects.get(username=options["user"])]
            except:
                print("No user with that username.")
                sys.exit(1)

        try:
            group = Group.objects.get(name=options["group"])
        except:
            print("No group with that name.")
            sys.exit(1)

        for user in users:
            if user not in group.user_set.all():
                sys.stderr.write("[NOTE] User %s added to group %s\n" % (user.username, group.name))
                group.user_set.add(user)

                group.save()
                treq = models.TatlPermFlex(
                    user = su,
                    substitute_user = None,
                    used_permission = "tatl.management.commands.grant_group",
                    timestamp = timezone.now(),
                    content_object = user,
                    extra_context = json.dumps({ "permissions_group": group.name, "permissions": [p.codename for p in group.permissions.all()] }),
                )
                treq.save()
