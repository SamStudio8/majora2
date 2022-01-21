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
                # Description
                desc = fields[0]
                if len(desc) == 0:
                    desc = name
            elif line_i == 3:
                # Entry point
                entry_point = fields[0]

                dv, created = models.MajoraDataview.objects.get_or_create(code_name=code, name=name, description=desc, entry_point=entry_point)
                dv.save()

            else:
                if fields[0] == "MF":
                    # Model field
                    f, created = models.MajoraDataviewSerializerField.objects.get_or_create(
                            dataview = dv,
                            model_name = fields[1],
                            model_field = fields[2],
                    )
                    f.save()

                elif fields[0] == "FF":
                    v = fields[4]
                    if fields[3] == "bool":
                        if v.lower() == "true":
                            v = 1
                        if v.lower() == "false":
                            v = 0

                    f, created = models.MajoraDataviewFilterField.objects.get_or_create(
                            dataview = dv,
                            filter_field = fields[1],
                            filter_op = fields[2],
                            filter_type = fields[3],
                            filter_value = v,
                    )
                    f.save()
