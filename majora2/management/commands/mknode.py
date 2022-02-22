from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Permission

from majora2 import models
from majora2 import util
from tatl import models as tmodels
from django.utils import timezone

class Command(BaseCommand):
    help = "Add a DigitalResourceNode"
    def add_arguments(self, parser):
        parser.add_argument('name')

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)

        node, created = util.mkroot(options["name"])
        if created:
            print("Node %s created" % node.unique_name)
            treq = tmodels.TatlPermFlex(
                user = su,
                substitute_user = None,
                used_permission = "majora2.management.commands.mkroot",
                timestamp = timezone.now(),
                content_object = node,
            )
            treq.save()
        else:
            print("Node %s already exists" % node.unique_name)
