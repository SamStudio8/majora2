import datetime

from django.test import Client, TestCase
from django.contrib.auth.models import User, Permission
from django.urls import reverse

from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_static.models import StaticDevice

from majora2.test import util

class DekuAdminTest(TestCase):
    def setUp(self):
        self.user_p = util.create_full_user("deku_user")
        self.user_nop = util.create_full_user("deku_scrub")

        # Assign admin requisite permissions
        p = Permission.objects.get(codename="change_profile")
        self.user_p.user_permissions.add(p)
        self.user_p.save()

        # Log the users in and mock an OTP (https://github.com/Bouke/django-two-factor-auth/issues/244)
        self.c_perm = Client()
        self.c_noperm = Client()

        self.c_perm.login(username='deku_user', password='password')
        self.c_noperm.login(username='deku_scrub', password='password')

        # Mock an OTP for admin
        device = StaticDevice.objects.get_or_create(user=self.user_p)[0]
        device.save()
        session = self.c_perm.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()

        # Mock an OTP for scrub
        device = StaticDevice.objects.get_or_create(user=self.user_nop)[0]
        device.save()
        session = self.c_noperm.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()

    def test_dekuadmin_can_list_profiles(self):
        response = self.c_perm.get(reverse('list_all_profiles'), secure=True)
        self.assertEqual(response.status_code, 200)

    def test_dekuscrub_cannot_list_profiles(self):
        response = self.c_noperm.get(reverse('list_all_profiles'), secure=True)
        self.assertEqual(response.status_code, 403)

