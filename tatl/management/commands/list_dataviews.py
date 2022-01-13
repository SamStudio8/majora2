from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2 import models
from django.contrib.auth.models import User, Permission

from tatl import models

import sys
import json

class Command(BaseCommand):
    help = "Dump a list of dataview permissions for all users"

    def handle(self, *args, **options):
        for user in User.objects.all():
            if hasattr(user, "profile"):
                site_code = user.profile.institute.code
            else:
                continue

            for perm in user.profile.majoradataviewuserpermission_set.all():
                print("\t".join([
                    user.username,
                    site_code,
                    "majora2",
                    "dataview",
                    perm.dataview.code_name,
                    "directly_assigned",
                    perm.validity_end.strftime("%Y-%m-%d"),
                    "expired" if perm.is_expired or perm.is_revoked else "active",
                ]))
