from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2 import models
from django.contrib.auth.models import User, Permission, Group

from tatl import models

import sys
import json

class Command(BaseCommand):
    help = "Create a user group"
    def add_arguments(self, parser):
        parser.add_argument('group')
        parser.add_argument('permissions')

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)

        # Make Group
        group, created = Group.objects.get_or_create(name=options["group"])
        if group:
            sys.stderr.write("[NOTE] %s group %s\n" % (group.name, "CREATED" if created else "RETRIEVED"))

        if '&' in permissions:
            sep = '&'
        elif ' ' in permissions:
            sep = ' '
        else:
            sys.stderr.write("[FAIL] Cannot determine permission separator, use space or ampersand!\n")
            sys.exit(1)

        valid_permissions = []
        for p in options["permissions"].split(sep):
            p = p.split('.')[-1]
            try:
                permission = Permission.objects.get(codename=p)
            except:
                print("No permission with name %s" % p)
                continue

            if permission not in group.permissions.all():
                valid_permissions.append(permission.codename)
                group.permissions.add(permission)
                sys.stderr.write("[NOTE] %s permission assigned to group\n" % (permission.codename))

        if len(valid_permissions) > 0:
            group.save()
            treq = models.TatlPermFlex(
                user = su,
                substitute_user = None,
                used_permission = "tatl.management.commands.mkgroup",
                timestamp = timezone.now(),
                content_object = group,
                extra_context = json.dumps({ "permissions": valid_permissions }),
            )
            treq.save()
        else:
            sys.stderr.write("[NOTE] No permissions added to group\n")
