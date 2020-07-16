from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import slugify

from majora2 import models

import datetime

class Command(BaseCommand):
    help = "Load an dataview definition"
    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, *args, **options):
        fh = open(options["filename"])

        code = None
        name = None
        desc = None
        for line_i, line in enumerate(fh):
            fields = line.strip().split('\t')

            if line_i == 0:
                code = fields[0]
            elif line_i == 1:
                name = fields[0]
            elif line_i == 2:
                desc = fields[0]
                if len(desc) == 0:
                    desc = name

                dv, created = models.MajoraDataview.objects.get_or_create(code_name=code, name=name, description=desc)
                dv.save()
            else:
                f, created = models.MajoraDataviewSerializerField.objects.get_or_create(
                        dataview = dv,
                        model_name = fields[0],
                        model_field = fields[1],
                )
                f.save()

