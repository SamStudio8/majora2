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
def mask():
    return mark_safe('<img src="/static/mask_50.png" height="15px" alt="Mask of Majora" title="You\'ve met with a terrible fate, haven\'t you?" />')

@register.simple_tag
def instance_name():
    return mark_safe(getattr(settings, "INSTANCE_NAME", ""))

@register.simple_tag
def instance_colour():
    return mark_safe(getattr(settings, "INSTANCE_COLOUR", ""))
