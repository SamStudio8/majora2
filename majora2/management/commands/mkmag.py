from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User, Permission

from majora2 import models
from majora2 import util
from tatl import models as tmodels
from django.utils import timezone

class Command(BaseCommand):
    help = "Load a list of MAGs"
    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, *args, **options):
        su = User.objects.get(is_superuser=True)
        fh = open(options["filename"])

        seen_mags = set([])
        for i, line in enumerate(fh):
            if i == 0:
                # Root node
                node = util.mkroot(line.strip())

            else:
                mags, created = util.mkmag(line.strip(), sep='/', parents=True, artifact=False, physical=False, root=node)
                if sum(created) > 0:
                    for m in [mag for i, mag in enumerate(mags) if created[i]]:
                        treq = tmodels.TatlPermFlex(
                            user = su,
                            substitute_user = None,
                            used_permission = "majora2.management.commands.mkmag",
                            timestamp = timezone.now(),
                            content_object = m,
                        )
                        treq.save()
                for m in mags:
                    if m.id in seen_mags:
                        continue
                    print("\t".join([
                        str(m.id),
                        m.group_path
                    ]))
                    seen_mags.add(m.id)
