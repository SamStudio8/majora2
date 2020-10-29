import datetime

from django.contrib.auth.models import User

from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_static.models import StaticDevice

from majora2 import models

def create_full_user(username):
    hoot = models.Institute(code="HOOT", name="Hypothetical University of Hooting")
    hoot.save()

    # Create a fully approved profile user with otp
    user = User.objects.create(username=username, email='%s@example.org' % username)
    user.set_password('password')
    user.is_active = True
    user.save()
    profile = models.Profile(user=user, institute=hoot, is_site_approved=True)
    profile.save()
    return user
