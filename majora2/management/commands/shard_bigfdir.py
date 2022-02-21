import sys
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from majora2 import models
from majora2 import util
from tatl import models as tmodels

from django.contrib.auth.models import User

class Command(BaseCommand):
    help = "Read a shard manifest and move the associated Digital Resource Artifacts"
    def add_arguments(self, parser):
        parser.add_argument('--filename', help="Bulk move a tab-delimited table of files (new_mv, old_mag, old_name, new_mag, new_name, new_path)", required=True)
        parser.add_argument('--username', help="Username of user to blame this on", required=True)
        parser.add_argument("--view-name", help="TatlRequest.view_name", required=True)
        parser.add_argument("--param", help="key:value to add to TatlRequest.params", action='append', nargs=2, metavar=('key', 'value'))
        parser.add_argument("--node", help="DigitalResourceNode", default="climb")


    def handle(self, *args, **options):

        mag_cache = {}

        user = User.objects.get(username=options["username"])
        if not user:
            sys.stderr.write("No such user\n")
            sys.exit(1)

        params_d = {x[0]: x[1] for x in options["param"]}
        try:
            json_params = json.dumps(params_d)
        except:
            sys.stderr.write("Could not transform --param to JSON\n")
            sys.exit(1)

        treq = tmodels.TatlRequest(user=user, view_name=options["view_name"], is_api=False)
        treq.status_code = 0
        treq.params = json_params
        treq.timestamp = timezone.now()
        treq.save()

        fh = open(options["filename"])

        for line in fh:
            new_mv, old_mag, old_name, new_mag, new_name, new_path = line.strip().split('\t')
            if int(new_mv) > 0:
                exit, dra = self.mv(mag_cache=mag_cache, treq=treq, node=options["node"], src_mag=old_mag, src_name=old_name, dest_mag=new_mag, dest_name=new_name, dest_path=new_path)
                print(exit, old_mag, old_name)

    def mv(self, mag_cache, treq, node, src_mag, src_name, dest_mag, dest_name, dest_path):
        src_mag_o = None
        if src_mag not in mag_cache:
            src_mag_o = util.get_mag(node, src_mag)
            if src_mag_o:
                mag_cache[src_mag] = src_mag_o
        else:
            src_mag_o = mag_cache[src_mag]

        if not src_mag_o:
            return 1, None

        try:
            dra = models.DigitalResourceArtifact.objects.get(primary_group=src_mag_o, current_name=src_name)
        except models.DigitalResourceArtifact.DoesNotExist:
            return 2, None

        dest_mag_o = None
        if dest_mag not in mag_cache:
            dest_mag_o = util.get_mag(node, dest_mag)
            if dest_mag_o:
                mag_cache[dest_mag] = dest_mag_o
        else:
            dest_mag_o = mag_cache[dest_mag]

        if not dest_mag_o:
            mags, mags_created = util.mkmag(root=models.DigitalResourceNode.objects.get(unique_name=node), path=dest_mag)
            dest_mag_o = mags[-1]

        if not dest_mag_o:
            return 2, None

        dra.current_path = dest_path
        dra.primary_group = dest_mag_o
        dra.save()

        # Flex verb
        tmodels.TatlVerb(request=treq, verb="UPDATE", content_object=dra,
            extra_context = json.dumps({
            }),
        ).save()
        return 0, dra
