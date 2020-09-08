from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2 import models
from django.contrib.auth.models import User, Permission

from tatl import models

import sys
import json

class Command(BaseCommand):
    help = "Dump a list of application permissions for all users"

    def handle(self, *args, **options):
        for user in User.objects.all():
            site_code = "----"
            if hasattr(user, "profile"):
                site_code = user.profile.institute.code
            for perm in user.user_permissions.all():
                print("\t".join([
                    user.username,
                    site_code,
                    perm.content_type.app_label,
                    perm.content_type.name,
                    perm.codename,
                    'directly_assigned',
                ]))
            for group in user.groups.all():
                for perm in group.permissions.all():
                    print("\t".join([
                        user.username,
                        site_code,
                        perm.content_type.app_label,
                        perm.content_type.name,
                        perm.codename,
                        group.name,
                    ]))
