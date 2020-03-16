# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from . import models

admin.site.register(models.Node)
admin.site.register(models.Resource)
admin.site.register(models.ResourceGroup)
admin.site.register(models.Command)
admin.site.register(models.CommandOnResource)
admin.site.register(models.MetaRecord)
