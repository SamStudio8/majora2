import csv
import json
from urllib.parse import unquote


from django.core.management.base import BaseCommand, CommandError

from majora2 import models
from majora2 import forms
from majora2 import form_handlers
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = "Load samples from a headered tsv"
    def add_arguments(self, parser):
        parser.add_argument('filename')
        parser.add_argument('username')
        parser.add_argument('orgcode')
        parser.add_argument("--initial", required=True, help="JSON configuration string for this operation")

    def handle(self, *args, **options):
        print("DONT USE THIS YET MATEY")
        import sys; sys.exit(8)
        reader = csv.DictReader(open(options['filename'], 'r'), dialect='excel-tab')
        initial = json.loads(unquote(options['initial'].replace('\'', '"')))
        user = User.objects.get(username=options["username"])
        org = models.Institute.objects.get(code=options["orgcode"])

        for row in reader:
            form = forms.TestSampleForm(row, initial=initial)
            form.data['override_heron'] = True
            if form.is_valid():
                if form_handlers.handle_testsample(form, user):
                    print("OK")
            print(form._errors)
