# Generated by Django 2.2.13 on 2020-11-05 15:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('majora2', '0132_auto_20201103_1223'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='profile',
            options={'permissions': [('can_revoke_profiles', 'Can revoke the access of any user'), ('can_approve_profiles', 'Can approve new user profiles for their organisation'), ('can_approve_profiles_via_bot', 'Can approve new user profiles for any organisation via the bot system'), ('can_grant_profile_permissions', 'Can grant other users permissions that change the Profile system')]},
        ),
        migrations.AddField(
            model_name='profile',
            name='is_revoked',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='profile',
            name='revoked_reason',
            field=models.CharField(blank=True, max_length=24, null=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='revoked_timestamp',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
