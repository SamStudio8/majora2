# Generated by Django 2.2.13 on 2021-05-25 21:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('majora2', '0140_auto_20210427_1746'),
    ]

    operations = [
        migrations.AlterField(
            model_name='majoradataviewfilterfield',
            name='filter_type',
            field=models.CharField(choices=[('str', 'str'), ('int', 'int'), ('float', 'float'), ('bool', 'bool'), ('list', 'list')], max_length=8),
        ),
    ]