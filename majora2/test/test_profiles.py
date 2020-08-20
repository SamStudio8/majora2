from django.test import Client, TestCase
from django.contrib.auth.models import User

class ProfileTest(TestCase):
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
