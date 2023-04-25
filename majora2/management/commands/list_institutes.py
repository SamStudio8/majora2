from django.core.management.base import BaseCommand
from majora2.models import Institute

class Command(BaseCommand):
    help = "Dump a table of institutes"

    def handle(self, *args, **options):
        for institute in Institute.objects.all():
            print("\t".join(
                [                        
                    institute.code, 
                    institute.name, 
                    "ena_opted_in" if institute.ena_opted else "ena_opted_out",
                    "ena_assembly_opted_in" if institute.ena_assembly_opted else "ena_assembly_opted_out",
                    "gisaid_opted_in" if institute.gisaid_opted else "gisaid_opted_out"
                ]
            )
        )
