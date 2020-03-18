from django.core.management.base import BaseCommand, CommandError

from majora2 import models

class Command(BaseCommand):
    help = "Load a list of organisations"
    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, *args, **options):
        fh = open(options["filename"])
        for line in fh:
            fields = line.strip().split('\t')
            code = fields[1]
            name = fields[0]
            org, created = models.Institute.objects.get_or_create(code=code, name=name)
            org.save()

