# Generated by Django 2.2.13 on 2020-08-22 17:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tatl', '0018_auto_20200822_1710'),
    ]

    operations = [
        migrations.AddField(
            model_name='tatlrequest',
            name='status_code',
            field=models.PositiveSmallIntegerField(default=0),
            preserve_default=False,
        ),
    ]
