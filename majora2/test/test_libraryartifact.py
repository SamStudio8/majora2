from django.urls import reverse

from majora2 import models
from tatl import models as tmodels
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

        library = models.LibraryArtifact.objects.get(dice_name=library_name)
        assert library.layout_config == payload.get("library_layout_config")
        assert library.layout_read_length == payload.get("library_layout_read_length")
        assert library.layout_insert_length == payload.get("library_layout_insert_length")
        assert library.seq_kit == payload.get("library_seq_kit")
        assert library.seq_protocol == payload.get("library_seq_protocol")

    def test_add_library_twice_no_update(self):
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
        library = models.LibraryArtifact.objects.get(dice_name=library_name)

        # Confirm CREATED verb
        j = response.json()
        tatl = tmodels.TatlRequest.objects.filter(response_uuid=j["request"]).first()
        self.assertIsNotNone(tatl)
        self.assertEqual(tatl.verbs.count(), 2)
        expected_verbs = [
            ("CREATE", library),
            ("UPDATE", bs),
        ]
        for verb in tatl.verbs.all():
            self.assertIn( (verb.verb, verb.content_object), expected_verbs )

        # Add library again
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        # Confirm no UPDATE verb
        j = response.json()
        tatl = tmodels.TatlRequest.objects.filter(response_uuid=j["request"]).first()
        self.assertIsNotNone(tatl)
        self.assertEqual(tatl.verbs.count(), 0)

    def test_update_library(self):
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

        # Create
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        payload["library_seq_kit"] = "NEWKIT"
        payload["library_seq_protocol"] = "NEWPROTOCOL"

        # Update
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)
        library = models.LibraryArtifact.objects.get(dice_name=library_name)

        # Assert changes
        assert library.seq_kit == payload.get("library_seq_kit")
        assert library.seq_protocol == payload.get("library_seq_protocol")

        # Confirm UPDATE verb
        j = response.json()
        tatl = tmodels.TatlRequest.objects.filter(response_uuid=j["request"]).first()
        self.assertIsNotNone(tatl)
        self.assertEqual(tatl.verbs.count(), 1)
        expected_verbs = [
            ("UPDATE", library),
        ]
        for verb in tatl.verbs.all():
            self.assertIn( (verb.verb, verb.content_object), expected_verbs )


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

