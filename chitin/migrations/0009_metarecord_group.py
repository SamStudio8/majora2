# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chitin_meta', '0008_auto_20181119_1152'),
    ]

    operations = [
        migrations.AddField(
            model_name='metarecord',
            name='group',
            field=models.ForeignKey(blank=True, to='chitin_meta.ResourceGroup', null=True),
        ),
    ]
