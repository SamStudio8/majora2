from django.core.management.base import BaseCommand, CommandError

from majora2 import models

class Command(BaseCommand):
    help = "Load a list of counties"
    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, *args, **options):
        fh = open(options["filename"])
        for line in fh:
            fields = line.strip().split('\t')
            country_code = fields[0]
            name = fields[1]
            c, created = models.County.objects.get_or_create(country_code=country_code, name=name)
            c.save()

