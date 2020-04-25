from django.core.management.base import BaseCommand, CommandError

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
                test_set_name = fields[0]
                test, test_created = models.PAGQualityTest.objects.get_or_create(name=test_set_name)
                test.save()
            elif line_i == 1:
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
                else:
                    continue






