# Generated by Django 2.2.10 on 2020-03-18 17:37

from django.db import migrations
import uuid

def make_keys(apps, schema_editor):
    Profile = apps.get_model("majora2", "Profile")
    for profile in Profile.objects.all():
        profile.api_key = uuid.uuid4()
        profile.save()

class Migration(migrations.Migration):

    dependencies = [
        ('majora2', '0008_profile_api_key'),
    ]

    operations = [
        migrations.RunPython(make_keys),
    ]