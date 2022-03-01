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
                "active" if user.is_active else "inactive", 
            ]))
