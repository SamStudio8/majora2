# Generated by Django 2.2.13 on 2020-08-07 11:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tatl', '0005_auto_20200527_1328'),
    ]

    operations = [
        migrations.AddField(
            model_name='tatlrequest',
            name='response_time',
            field=models.DurationField(blank=True, null=True),
        ),
    ]