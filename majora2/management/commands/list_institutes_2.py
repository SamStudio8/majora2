from django.core.management.base import BaseCommand
from majora2.models import Institute


class Command(BaseCommand):
    help = "Dump a different table of institutes"

    def handle(self, *args, **options):
        ena_opted_in = []
        ena_opted_out = []
        ena_assembly_opted_in = []
        ena_assembly_opted_out = []
        gisaid_opted_in = []
        gisaid_opted_out = []
        for institute in Institute.objects.all():
            if institute.ena_opted:
                ena_opted_in.append([institute.code, institute.name])
            else:
                ena_opted_out.append([institute.code, institute.name])
            if institute.ena_assembly_opted:
                ena_assembly_opted_in.append([institute.code, institute.name])
            else:
                ena_assembly_opted_out.append([institute.code, institute.name])
            if institute.gisaid_opted:
                gisaid_opted_in.append([institute.code, institute.name])
            else:
                gisaid_opted_out.append([institute.code, institute.name])

        print("ENA_OPTED_IN")
        for x in ena_opted_in:
            print("\t".join(x))
        print("\nENA_OPTED_OUT")
        for x in ena_opted_out:
            print("\t".join(x))
        print("\nENA_ASSEMBLY_OPTED_IN")
        for x in ena_assembly_opted_in:
            print("\t".join(x))
        print("\nENA_ASSEMBLY_OPTED_OUT")
        for x in ena_assembly_opted_out:
            print("\t".join(x))
        print("\nGISAID_OPTED_IN")
        for x in gisaid_opted_in:
            print("\t".join(x))
        print("\nGISAID_OPTED_OUT")
        for x in gisaid_opted_out:
            print("\t".join(x))
