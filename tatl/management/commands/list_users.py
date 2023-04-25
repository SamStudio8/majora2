from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2 import models
from django.contrib.auth.models import User, Permission

from tatl import models

import sys
import json

class Command(BaseCommand):
    help = "Dump a table of users"

    def handle(self, *args, **options):
        for user in User.objects.all():
            site_code = "----"
            if hasattr(user, "profile"):
                site_code = user.profile.institute.code

            print('\t'.join([
                user.username,
                user.email,
                user.first_name,
                user.last_name,
                site_code,
                "is_site_approved" if hasattr(user, "profile") and user.profile.is_site_approved else "not_site_approved",
                "is_active" if user.is_active else "not_active",
                "is_revoked" if hasattr(user, "profile") and user.profile.is_revoked else "not_revoked",
                "is_staff" if user.is_staff else "not_staff",
                "is_superuser" if user.is_superuser else "not_superuser",
                str(user.last_login),
            ]))
