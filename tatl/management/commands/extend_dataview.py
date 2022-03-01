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
    help = "Extend dataview access to all active users with permission"
    def add_arguments(self, parser):
        parser.add_argument('dataview')
        parser.add_argument('--date', required=True)
        parser.add_argument('--expired', action="store_true", help="extend expired dataviews (not extended by default)")

    def handle(self, *args, **options):
        now = timezone.now()

        su = User.objects.get(is_superuser=True)
        try:
            mdv = models.MajoraDataview.objects.get(code_name=options["dataview"])
        except:
            print("No dataview with that name.")
            sys.exit(1)

        end = datetime.datetime.strptime(options["date"], "%Y-%m-%d")

        # Already has perm?
        for perm in models.MajoraDataviewUserPermission.objects.filter(dataview=mdv):
            action = "ignore"
            reason = "-"

            # If the user is still active and the permission was not revoked
            if not perm.profile.user.is_active:
                reason = "inactive"
            elif perm.is_revoked:
                reason = "revoked"
            elif perm.validity_end < now and not options["expired"]:
                # Perm is expired AND the --expired option is unset
                reason = "expired"
            else:
                action = "extend"


            if action == "extend":
                perm.validity_end = end
                perm.save()

                treq = tmodels.TatlPermFlex(
                    user = su,
                    substitute_user = None,
                    used_permission = "tatl.management.commands.extend_dataview",
                    timestamp = now,
                    content_object = perm.profile,
                    extra_context = json.dumps({
                        "dataview": mdv.code_name,
                        "dataview_permission": perm.id,
                        "dataview_action": action,
                        "validity_end": perm.validity_end.strftime("%Y-%m-%d %H:%M:%S"),
                    }),
                )
                treq.save()

            print('\t'.join([
                mdv.code_name,
                perm.profile.user.username,
                action,
                str(perm.validity_end),
                reason,
            ]))


