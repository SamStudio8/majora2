# Generated by Django 2.2.13 on 2020-08-28 13:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tatl', '0024_oauth2codeonlyapplication'),
    ]

    operations = [
        migrations.AlterField(
            model_name='oauth2codeonlyapplication',
            name='authorization_grant_type',
            field=models.CharField(choices=[('authorization-code', 'Authorization code')], max_length=32),
        ),
    ]