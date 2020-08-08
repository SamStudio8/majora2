from django.core.management.base import BaseCommand, CommandError

from majora2 import models
from majora2 import util
from tatl import models as tmodels

from django.utils import timezone

class Command(BaseCommand):
    help = "Initialise basic COG MAGs"

    def handle(self, *args, **options):
        maj_root = util.mkroot("majora")
        for pag in models.PublishedArtifactGroup.objects.all():
            if pag.published_name.startswith("COGUK"):
                root, central_sample_id, run_name = pag.published_name.split("/")
                run_site, run_name = run_name.split(":")

                try:
                    biosample = pag.tagged_artifacts.get(biosampleartifact__isnull=False)
                except:
                    print(pag.published_name, "has 0 or more than one BSA")
                    continue

                # by sample id
                mags, created = util.mkmag("/COGUK/seqs/%s" % central_sample_id, sep="/", parents=True, artifact=False, physical=False, root=maj_root, kind="test")
                mag = mags[-1]
                mag.groups.add(pag)
                print("\t".join([
                    str(mag.id),
                    mag.group_path,
                    str(pag.id),
                    pag.published_name
                ]))
                seq_mag = mag

                # by heron
                
                # by source site
                source_site = biosample.created.who.profile.institute.code
                mags, created = util.mkmag("/COGUK/seqs-by-sourcesite/%s" % source_site, sep="/", parents=True, artifact=False, physical=False, root=maj_root, kind="test")
                mags, created = util.mkmag("/COGUK/seqs-by-sourcesite/%s/%s" % (source_site, central_sample_id), sep="/", parents=True, artifact=False, physical=False, root=maj_root, kind="test")
                mag = mags[-1]
                mag.groups.add(pag)

                # by seq site
                mags, created = util.mkmag("/COGUK/seqs-by-seqsite/%s" % run_site, sep="/", parents=True, artifact=False, physical=False, root=maj_root, kind="test")
                mags, created = util.mkmag("/COGUK/seqs-by-seqsite/%s/%s" % (run_site, central_sample_id), sep="/", parents=True, artifact=False, physical=False, root=maj_root, kind="test")
                mag = mags[-1]
                mag.groups.add(pag)

