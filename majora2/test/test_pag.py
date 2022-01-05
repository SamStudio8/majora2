from django.contrib.auth.models import User, Permission
from django.urls import reverse

from majora2 import models
from majora2.test.test_basic_api import OAuthAPIClientBase

import datetime

class OAuthSuppressPAGTest(OAuthAPIClientBase):
    def setUp(self):
        super().setUp()

        self.endpoint = reverse("api.group.pag.suppress")
        self.scope = "majora2.can_suppress_pags_via_api"
        self.token = self._get_token(self.scope)

        pag = models.PublishedArtifactGroup(
            published_name="HOOT/HOOT-BESAM5/HOOT:HOOTHOOT",
            published_version=1,
            is_latest=True,
            owner=self.user,
        )
        pag.save()

        fp = Permission.objects.get(codename="can_suppress_pags_via_api")
        self.user.user_permissions.add(fp)
        self.user.save()

        fp = Permission.objects.get(codename="can_suppress_any_pags_via_api")
        self.staff_user.user_permissions.add(fp)
        self.staff_user.save()

    def test_suppress_ok(self):
        payload = {
            "username": self.user.username,
            "token": "oauth",
            "publish_group": "HOOT/HOOT-BESAM5/HOOT:HOOTHOOT",
            "reason": "WRONG_SEQUENCE",
        }
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["errors"], 0)

        pag = models.PublishedArtifactGroup.objects.get(published_name="HOOT/HOOT-BESAM5/HOOT:HOOTHOOT")
        assert pag is not None
        assert pag.is_suppressed is True
        assert pag.suppressed_reason == "WRONG_SEQUENCE"
        assert pag.suppressed_date.date() == datetime.date.today()

    def test_suppress_already_pag(self):
        payload = {
            "username": self.user.username,
            "token": "oauth",
            "publish_group": "HOOT/HOOT-BESAM5/HOOT:HOOTHOOT",
            "reason": "WRONG_SEQUENCE",
        }
        pag = models.PublishedArtifactGroup.objects.get(published_name="HOOT/HOOT-BESAM5/HOOT:HOOTHOOT")
        pag.is_suppressed = True
        pag.save()

        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["warnings"], 1)
        self.assertIn("already suppressed", "".join(j["messages"]))

        pag = models.PublishedArtifactGroup.objects.get(published_name="HOOT/HOOT-BESAM5/HOOT:HOOTHOOT")
        assert pag is not None
        assert pag.is_suppressed is True

    def test_suppress_bad_pag(self):
        payload = {
            "username": self.user.username,
            "token": "oauth",
            "publish_group": "HOOT/HOOT-BESAM5/MEOW:MEOWMEOW",
            "reason": "WRONG_SEQUENCE",
        }
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["warnings"], 1)
        self.assertIn("not found", "".join(j["messages"]))

    def test_suppress_bad_reason(self):
        payload = {
            "username": self.user.username,
            "token": "oauth",
            "publish_group": "HOOT/HOOT-BESAM5/HOOT:HOOTHOOT",
            "reason": "NOT_ENOUGH_HOOTS",
        }
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["errors"], 1)
        self.assertIn("Reason must be one of", "".join(j["messages"]))

    def test_suppress_bad_scope(self):
        payload = {
            "username": self.user.username,
            "token": "oauth",
            "publish_group": "HOOT/HOOT-BESAM5/MEOW:MEOWMEOW",
            "reason": "WRONG_SEQUENCE",
        }
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.tokens["bad_scope"])
        self.assertEqual(200, response.status_code)
        j = response.json()
        self.assertEqual(j["errors"], 1)
        self.assertIn("Your token is valid but does not have all of the scopes to perform this action.", "".join(j["messages"]))

    def test_suppress_else_pag(self):
        pag = models.PublishedArtifactGroup(
            published_name="HOOO/HOOO-BESAM5/HOOO:HOOHOO",
            published_version=1,
            is_latest=True,
            owner=self.not_user,
        )
        pag.save()

        payload = {
            "username": self.user.username,
            "token": "oauth",
            "publish_group": "HOOO/HOOO-BESAM5/HOOO:HOOHOO",
            "reason": "WRONG_SEQUENCE",
        }
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["errors"], 1)
        self.assertIn("does not own", "".join(j["messages"]))

    def test_suppress_else_pag_as_admin(self):
        staff_token = self._get_token(self.scope, user=self.staff_user)

        pag = models.PublishedArtifactGroup(
            published_name="HOOO/HOOO-BESAM5/HOOO:HOOHOO",
            published_version=1,
            is_latest=True,
            owner=self.user,
        )
        pag.save()

        payload = {
            "username": self.staff_user.username,
            "token": "oauth",
            "publish_group": "HOOO/HOOO-BESAM5/HOOO:HOOHOO",
            "reason": "WRONG_SEQUENCE",
        }
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % staff_token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["errors"], 0)

        pag = models.PublishedArtifactGroup.objects.get(published_name="HOOO/HOOO-BESAM5/HOOO:HOOHOO")
        assert pag is not None
        assert pag.is_suppressed is True
        assert pag.suppressed_reason == "WRONG_SEQUENCE"
        assert pag.suppressed_date.date() == datetime.date.today()

