from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Permission

from majora2 import models
from tatl import models as tmodels
from django.utils import timezone

class Command(BaseCommand):
    help = "Load a list of organisations"
    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)
        fh = open(options["filename"])
        for line in fh:
            fields = line.strip().split('\t')
            code = fields[1]
            name = fields[0]
            org, created = models.Institute.objects.get_or_create(code=code, name=name)
            org.save()
            if created:
                treq = tmodels.TatlPermFlex(
                    user = su,
                    substitute_user = None,
                    used_permission = "majora2.management.commands.load_orgs",
                    timestamp = timezone.now(),
                    content_object = org,
                )
                treq.save()
