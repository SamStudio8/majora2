from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2 import models
from django.contrib.auth.models import User, Permission

from tatl import models as tmodels
from majora2 import models

import sys
import json
import datetime

class Command(BaseCommand):
    help = "Load API key definitions"
    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)
        fh = open(options["filename"])
        for line in fh:
            fields = line.strip().split('\t')
            key_name = fields[0]

            permission = None
            if len(fields[1]) > 0:
                try:
                    permission = Permission.objects.get(codename=fields[1])
                except:
                    print("No permission with that name. Skipping keydef %s" % key_name)
                    continue

            is_service = bool(int(fields[2]))
            is_read = bool(int(fields[3]))
            is_write = bool(int(fields[4]))
            lifespan_td = datetime.timedelta(seconds=int(fields[5])) # seconds

            keydef, created = models.ProfileAPIKeyDefinition.objects.get_or_create(
                                    key_name = key_name,
                                    is_service_key = is_service,
                                    is_read_key = is_read,
                                    is_write_key = is_write,
                                    lifespan = lifespan_td
            )
            keydef.permission = permission
            keydef.save()

            if created:
                treq = tmodels.TatlPermFlex(
                    user = su,
                    substitute_user = None,
                    used_permission = "tatl.management.commands.add_keydef",
                    timestamp = timezone.now(),
                    content_object = keydef,
                    extra_context = json.dumps({
                        "key_def": key_name
                    }),
                )
                treq.save()
