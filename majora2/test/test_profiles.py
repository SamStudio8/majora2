import datetime
from urllib.parse import urlencode

from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from majora2 import models

class BasicUserTest(TestCase):
    def setUp(self):
        self.c = Client()

        # Create a user, but do not approve them
        user = User.objects.create(username='unapproved_user', email='unapproved@example.org')
        user.set_password('password')
        user.is_active = False
        user.save()

        # Create a user, but do approve them
        user = User.objects.create(username='approved_user', email='approved@example.org')
        user.set_password('password')
        user.is_active = True
        user.save()

    def test_nologin_without_registered(self):
        can_login = self.c.login(username='not_registered', password='secret')
        self.assertFalse(can_login)

    def test_nologin_without_approval(self):
        can_login = self.c.login(username='unapproved_user', password='password')
        self.assertFalse(can_login)

    def test_login_with_approval(self):
        can_login = self.c.login(username='approved_user', password='password')
        self.assertTrue(can_login)

    def test_nologin_with_approval_badpass(self):
        can_login = self.c.login(username='approved_user', password='badpass')
        self.assertFalse(can_login)


class ProfileTest(TestCase):
    def setUp(self):
        self.c = Client()

        # Create an institute
        hoot = models.Institute(code="HOOT", name="Hypothetical University of Hooting")
        hoot.save()
        self.org = hoot

        # Create a user awaiting site approval
        user = User.objects.create(username='profiled_user_00', email='profile_00@example.org')
        user.set_password('password')
        user.is_active = False
        user.save()
        profile = models.Profile(user=user, institute=hoot, is_site_approved=False)
        profile.save()
        self.user_00 = user

        # Create a user awaiting syadmin approval
        user = User.objects.create(username='profiled_user_01', email='profile_10@example.org')
        user.set_password('password')
        user.is_active = False
        user.save()
        profile = models.Profile(user=user, institute=hoot, is_site_approved=True) # site leads mark this field
        profile.save()

        # Create a fully approved profile user
        user = User.objects.create(username='profiled_user_11', email='profile_11@example.org')
        user.set_password('password')
        user.is_active = True # sysadmins mark this field
        user.save()
        profile = models.Profile(user=user, institute=hoot, is_site_approved=True)
        profile.save()

    def test_profile_institute(self):
        self.assertEqual(self.org.code, self.user_00.profile.institute.code)
        self.assertEqual(self.org.name, self.user_00.profile.institute.name)


class ProfileAPIKeyTest(TestCase):
    def setUp(self):
        self.c = Client()

        # Create an institute and user profile
        hoot = models.Institute(code="HOOT", name="Hypothetical University of Hooting")
        hoot.save()

        # Create a fully approved profile user
        user = User.objects.create(username='profiled_user_11', email='profile_11@example.org')
        user.set_password('password')
        user.is_active = True # sysadmins mark this field
        user.save()
        profile = models.Profile(user=user, institute=hoot, is_site_approved=True)
        profile.save()

        self.user_0g1a = user

        # Create an API key def
        kd = models.ProfileAPIKeyDefinition(
                                            key_name = "Kipper's Magic Key",
                                            lifespan = datetime.timedelta(days=7),
                                            is_service_key=False,
                                            is_read_key=False,
                                            is_write_key=False,
        )
        kd.save()
        self.kd = kd

        # Log the user in and mock an OTP (https://github.com/Bouke/django-two-factor-auth/issues/244)
        from django_otp import DEVICE_ID_SESSION_KEY
        from django_otp.plugins.otp_static.models import StaticDevice

        self.c.login(username='profiled_user_11', password='password')
        device = StaticDevice.objects.get_or_create(user=user)[0]
        device.save()
        session = self.c.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()

    def test_profile_0g1a_apikey_is_available(self):
        self.assertEqual(1, len(self.user_0g1a.profile.get_available_api_keys()))

    def test_profile_0g1a_has_no_apikeys(self):
        self.assertEqual(0, len(self.user_0g1a.profile.get_generated_api_keys()))

    def test_profile_0g1a_can_activate_to_1g1a(self):
        response = self.c.post('/keys/activate/', {'key_name': self.kd.key_name}, secure=True)

        self.assertEqual(0, len(self.user_0g1a.profile.get_available_api_keys()))
        self.assertEqual(1, len(self.user_0g1a.profile.get_generated_api_keys()))

        self.user_0g1a.profile.get_generated_api_keys()[0].delete() # destroy the key

