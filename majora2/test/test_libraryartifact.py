from django.urls import reverse

from majora2 import models
from majora2.test.test_basic_api import OAuthAPIClientBase

class OAuthLibraryArtifactTest(OAuthAPIClientBase):
    def setUp(self):
        super().setUp()

        self.endpoint = reverse("api.artifact.library.add")
        self.scope = "majora2.add_biosampleartifact majora2.add_libraryartifact majora2.add_librarypoolingprocess majora2.change_biosampleartifact majora2.change_libraryartifact majora2.change_librarypoolingprocess"
        self.token = self._get_token(self.scope)

    def test_add_basic_library_ok(self):
        lib_count = models.LibraryArtifact.objects.count()

        # Biosample needs to exist to add a library (without forcing)
        bs = models.BiosampleArtifact(central_sample_id="HOOT-00001", dice_name="HOOT-00001")
        bs.save()

        library_name = "HOOT-LIB-1"
        payload = {
            "biosamples": [
                {
                    "central_sample_id": bs.dice_name,
                    "library_source": "VIRAL_RNA",
                    "library_selection": "PCR",
                    "library_strategy": "AMPLICON",
                }
            ],
            "library_layout_config": "SINGLE",
            "library_name": library_name,
            "library_seq_kit": "KIT",
            "library_seq_protocol": "PROTOCOL",
            "username": "OAUTH",
            "token": "OAUTH"
        }

        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        self.assertEqual(models.LibraryArtifact.objects.count(), lib_count + 1)
        assert models.LibraryArtifact.objects.filter(dice_name=library_name).count() == 1

    def test_m59_add_library_bad_biosamples_key(self):
        lib_count = models.LibraryArtifact.objects.count()

        library_name = "HOOT-LIB-1"
        payload = {
            "biosamples": { "central_sample_id": "HOOT-00001" },
            "library_name": library_name,
            "username": "OAUTH",
            "token": "OAUTH"
        }

        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["errors"], 1)
        self.assertIn("'biosamples' appears malformed", "".join(j["messages"]))

