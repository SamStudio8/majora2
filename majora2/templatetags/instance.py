from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def footer():
    return mark_safe("This instance of Majora (<b>%s</b>) is maintained by <b>%s</b>." % (
            getattr(settings, "INSTANCE_NAME", ""),
            getattr(settings, "INSTANCE_MAINTAINER", "")
    ))

@register.simple_tag
def instance_name():
    return mark_safe(getattr(settings, "INSTANCE_NAME", ""))

