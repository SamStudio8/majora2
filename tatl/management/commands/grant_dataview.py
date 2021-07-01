from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2 import models
from django.contrib.auth.models import User, Permission

from tatl import models as tmodels
from majora2 import models as models

import sys
import json
import datetime

class Command(BaseCommand):
    help = "Grant dataview access to a user"
    def add_arguments(self, parser):
        parser.add_argument('dataview')
        parser.add_argument('user')
        parser.add_argument('--date', required=False)

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)
        try:
            mdv = models.MajoraDataview.objects.get(code_name=options["dataview"])
        except:
            print("No dataview with that name.")
            sys.exit(1)

        try:
            user = User.objects.get(username=options["user"])
        except:
            print("No user with that username.")
            sys.exit(1)


        start = timezone.now()
        if options["date"]:
            end = datetime.datetime.strptime(options["date"], "%Y-%m-%d")
        else:
            end = start + datetime.timedelta(days=30)

        # Already has perm?
        p = models.MajoraDataviewUserPermission.objects.filter(
                profile = user.profile,
                dataview = mdv,
                validity_start__lt=start,
                validity_end__gt=start,
        ).first()

        if p:
            action = "extend"
            p.validity_end = end
        else:
            action = "grant"
            p = models.MajoraDataviewUserPermission(
                profile = user.profile,
                dataview = mdv,
                validity_start = start,
                validity_end = end
            )

        p.save()
        treq = tmodels.TatlPermFlex(
            user = su,
            substitute_user = None,
            used_permission = "tatl.management.commands.grant_dataview",
            timestamp = timezone.now(),
            content_object = user.profile,
            extra_context = json.dumps({
                "dataview": mdv.code_name,
                "dataview_permission": p.id,
                "dataview_action": action,
                "validity_end": p.validity_end.strftime("%Y-%m-%d %H:%M:%S"),
            }),
        )
        treq.save()
