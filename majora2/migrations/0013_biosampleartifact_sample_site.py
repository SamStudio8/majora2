# Generated by Django 2.2.10 on 2020-03-19 12:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('majora2', '0012_auto_20200319_1235'),
    ]

    operations = [
        migrations.AddField(
            model_name='biosampleartifact',
            name='sample_site',
            field=models.CharField(blank=True, max_length=24, null=True),
        ),
    ]