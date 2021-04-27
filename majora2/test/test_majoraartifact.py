from django.urls import reverse

from majora2.test.test_basic_api import OAuthAPIClientBase

class BiosampleArtifactInfoTest(OAuthAPIClientBase):
    def setUp(self):
        super().setUp()

        self.endpoint = reverse("api.artifact.info")
        self.scope = "majora2.view_majoraartifact_info"
        self.token = self.tokens["majora2.view_majoraartifact_info"]

    def test_get_majoraartifact_info_notoken(self):
        # Access should be rejected without a Bearer
        payload = {}

        response = self.c.get(self.endpoint, payload, secure=True, content_type="application/json")
        self.assertEqual(400, response.status_code)

        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json")
        self.assertEqual(400, response.status_code)

    def test_get_majoraartifact_info_badtoken(self):
        # Access should be rejected for an incorrect Bearer
        payload = {}

        response = self.c.get(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % "00000000")
        self.assertEqual(400, response.status_code)

        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % "00000000")
        self.assertEqual(400, response.status_code)

    def test_get_majoraartifact_info_wrongscope(self):
        # Access should be rejected for a valid Bearer with the wrong scope
        payload = {}
        token = self.tokens["bad_scope"]

        response = self.c.get(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % token)
        self.assertEqual(200, response.status_code)
        j = response.json()
        self.assertEqual(j["errors"], 1)
        self.assertIn("Your token is valid but does not have all of the scopes to perform this action.", "".join(j["messages"]))

        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % token)
        self.assertEqual(400, response.status_code) # no post

    def test_get_majoraartifact_info_missing_q(self):
        # Access should be granted over GET and rejected over POST for a valid Bearer (and scope), but report an error for no q param
        payload = {}

        response = self.c.get(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)
        j = response.json()
        self.assertEqual(j["errors"], 1)
        self.assertIn("'q' GET param missing or empty", j["messages"])

        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(400, response.status_code) # no post

    def test_get_majoraartifact_info_missing_artifact(self):
        # Report an error for no artifact matching q
        payload = {
            'q': "HOOT"
        }

        response = self.c.get(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)
        j = response.json()
        self.assertEqual(j["errors"], 1)
        self.assertIn("No artifact for query.", j["messages"])

