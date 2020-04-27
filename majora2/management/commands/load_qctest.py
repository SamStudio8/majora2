from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import slugify

from majora2 import models

import datetime

class Command(BaseCommand):
    help = "Load a QC test definition"
    def add_arguments(self, parser):
        parser.add_argument('filename')

    def handle(self, *args, **options):
        fh = open(options["filename"])
        rules = {}
        for line_i, line in enumerate(fh):
            fields = line.strip().split('\t')

            if line_i == 0:
                test_group_name = fields[0]
                test_egroup, test_egoup_created = models.PAGQualityTestEquivalenceGroup.objects.get_or_create(name=test_group_name, slug=slugify(test_group_name))
                test_egroup.save()
                print(test_egroup.slug)
            if line_i == 1:
                test_set_name = fields[0]
                test, test_created = models.PAGQualityTest.objects.get_or_create(name=test_set_name, group=test_egroup, slug=slugify(test_set_name))
                test.save()
            elif line_i == 2:
                version_number = int(fields[0])
                version_date = datetime.datetime.strptime(fields[1], "%Y-%m-%d")
                tv, tv_created = models.PAGQualityTestVersion.objects.get_or_create(test=test, version_number=version_number, version_date=version_date)
                tv.save()
            else:
                if line.startswith("R"):
                    thresholds = []
                    for f in fields[5:9]:
                        try:
                            thresholds.append(float(f))
                        except ValueError:
                            thresholds.append(None)
                    warn_min, warn_max, fail_min, fail_max = thresholds
                    rule, rule_created = models.PAGQualityTestRule.objects.get_or_create(
                            test=tv,
                            rule_name=fields[1],
                            rule_desc=fields[2],
                            metric_namespace=fields[3],
                            metric_name=fields[4],
                            warn_min=warn_min,
                            warn_max=warn_max,
                            fail_min=fail_min,
                            fail_max=fail_max,
                    )
                    rule.save()
                    rules[fields[1]] = rule

                elif line.startswith("D"):
                    a_name = fields[1]
                    b_name = fields[3]
                    op = fields[2]
                    if op != "OR" and op != "AND" and op is not None:
                        print("Invalid op... Skipping decision line")
                        continue
                    if op and not b_name:
                        print("Cannot set op without rule_b... Skipping decision line")
                        continue
                    if a_name not in rules or b_name not in rules:
                        print("Rules cannot be found in test set... Skipping decision line")
                        continue

                    decision, decision_created = models.PAGQualityBasicTestDecision.objects.get_or_create(
                            test=tv,
                            a=rules[a_name],
                            b=rules[b_name],
                            op=op,
                    )
                elif line.startswith("F"):
                    op = fields[6]
                    if op != "EQ" and op != "NEQ" and op is not None:
                        print("Invalid op... Skipping filter line")
                        continue
                    tfilter, tfilter_created = models.PAGQualityTestFilter.objects.get_or_create(
                            test=test,
                            filter_name=fields[1],
                            filter_desc=fields[2],
                            metadata_namespace=fields[3],
                            metadata_name=fields[4],
                            filter_on_str=fields[5],
                            op=op,
                    )
                else:
                    continue






