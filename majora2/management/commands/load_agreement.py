from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import slugify

from majora2 import models

import datetime

class Command(BaseCommand):
    help = "Load an agreement definition"
    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, *args, **options):
        fh = open(options["filename"])

        agreement_slug = None
        agreement_name = None
        agreement_desc = None
        agreement_version = None
        agreement_start = None
        agreement_proposed = None
        agreement_content = []

        for line_i, line in enumerate(fh):
            fields = line.strip().split('\t')

            if line_i == 0:
                agreement_slug = fields[0]
            elif line_i == 1:
                agreement_name = fields[0]
            elif line_i == 2:
                agreement_desc = fields[0]
                if len(agreement_desc) == 0:
                    agreement_desc = agreement_name
            elif line_i == 3:
                agreement_version = int(fields[0])
                agreement_proposed = datetime.datetime.strptime(fields[1], "%Y-%m-%d")
                if len(fields) > 2:
                    agreement_start = datetime.datetime.strptime(fields[2], "%Y-%m-%d")
            elif line_i == 4:
                pass
            else:
                agreement_content.append(line.strip())

        agreement = models.ProfileAgreementDefinition.objects.filter(slug=agreement_slug).first()
        if not agreement:
            agreement = models.ProfileAgreementDefinition()
            agreement.slug = agreement_slug
        agreement.name = agreement_name
        agreement.description = agreement_desc
        agreement.content = "\n".join(agreement_content)
        agreement.version = agreement_version
        agreement.proposal_timestamp = agreement_proposed
        agreement.effective_timestamp = agreement_start
        agreement.save()
