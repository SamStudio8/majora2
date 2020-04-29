from django import template

register = template.Library()

from majora2 import models

@register.simple_tag
def get_basic_qc(pag):
    report = models.PAGQualityReportEquivalenceGroup.objects.filter(pag=pag, test_group__slug="cog-uk-elan-minimal-qc").first()
    if report:
        return report.is_pass
    else:
        return None
@register.simple_tag
def get_public_qc(pag):
    report = models.PAGQualityReportEquivalenceGroup.objects.filter(pag=pag, test_group__slug="cog-uk-high-quality-public").first()
    if report:
        return report.is_pass
    else:
        return None
