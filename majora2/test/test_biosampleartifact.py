import datetime
import uuid

from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from majora2 import models
from majora2.test.test_basic_api import BasicAPITest

class BiosampleArtifactTest(BasicAPITest):
    def setUp(self):
        super().setUp()
        self.default_central_sample_id = "HOOT-00001"
        self.default_payload = {
            "username": self.user.username,
            "token": self.key.key,
            "biosamples": [
                {
                    "adm1": "UK-ENG",
                    "central_sample_id": self.default_central_sample_id,
                    "collection_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "is_surveillance": False,

                    "received_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "adm2": "Birmingham",
                    "source_age": 30,
                    "source_sex": "M",
                    "adm2_private": "B20",
                    "biosample_source_id": "ABC12345",
                    "collecting_org": "Hypothetical University of Hooting",
                    "collection_pillar": 1,
                    "root_sample_id": "PHA_12345",
                    "sample_type_collected": "swab",
                    "sample_type_received": "primary",
                    "sender_sample_id": "LAB12345",
                    "swab_site": "nose-throat",
                    "metadata": {
                        "test": {
                            "bubo": "bubo",
                            "hoots": 8,
                            "hooting": False,

                        },
                        "majora": {
                            "mask": "creepy",
                        }
                    }
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }

    def _add_biosample(self):
        response = self.c.post(reverse('api.artifact.biosample.add'), self.default_payload, secure=True, content_type="application/json")
        self.assertEqual(200, response.status_code)

        j = response.json()
        if j["errors"] != 0:
            sys.stderr.write(json.dumps(j, indent=4, sort_keys=True) + '\n')
        self.assertEqual(0, j["errors"])
        bs = models.BiosampleArtifact.objects.get(central_sample_id=self.default_central_sample_id)
        return bs

    def test_biosample_add(self):
        n_biosamples = models.BiosampleArtifact.objects.count()
        bs = self._add_biosample()
        self.assertEqual(models.BiosampleArtifact.objects.count(), n_biosamples+1)

        self.assertEqual(self.default_payload["biosamples"][0]["adm1"], bs.created.collection_location_adm1)
        self.assertEqual(self.default_payload["biosamples"][0]["central_sample_id"], bs.dice_name)
        self.assertEqual(datetime.datetime.strptime(self.default_payload["biosamples"][0]["collection_date"], "%Y-%m-%d").date(), bs.created.collection_date)
        self.assertEqual(self.default_payload["biosamples"][0]["is_surveillance"], bs.created.coguk_supp.is_surveillance)


        self.assertEqual(datetime.datetime.strptime(self.default_payload["biosamples"][0]["received_date"], "%Y-%m-%d").date(), bs.created.received_date)
        self.assertEqual(self.default_payload["biosamples"][0]["adm2"].upper(), bs.created.collection_location_adm2) # adm2 co-erced to upper
        self.assertEqual(self.default_payload["biosamples"][0]["source_age"], bs.created.source_age)
        self.assertEqual(self.default_payload["biosamples"][0]["source_sex"], bs.created.source_sex)

        biosample_sources = []
        for record in bs.created.records.all():
            if record.in_group and record.in_group.kind == "Biosample Source":
                biosample_sources.append(record.in_group.secondary_id)
        self.assertEqual(len(biosample_sources), 1)
        self.assertEqual(self.default_payload["biosamples"][0]["biosample_source_id"], biosample_sources[0])

        self.assertEqual(self.default_payload["biosamples"][0]["collecting_org"], bs.created.collected_by)
        self.assertEqual(self.user, bs.created.submission_user)
        self.assertEqual(self.user.profile.institute, bs.created.submission_org)
        self.assertEqual(self.user.profile.institute.name, bs.created.submitted_by)

        self.assertEqual(self.default_payload["biosamples"][0]["collection_pillar"], bs.created.coguk_supp.collection_pillar)
        self.assertEqual(self.default_payload["biosamples"][0]["root_sample_id"], bs.root_sample_id)
        self.assertEqual(self.default_payload["biosamples"][0]["sample_type_collected"], bs.sample_type_collected)
        self.assertEqual(self.default_payload["biosamples"][0]["sample_type_received"], bs.sample_type_current)
        self.assertEqual(self.default_payload["biosamples"][0]["sender_sample_id"], bs.sender_sample_id)
        self.assertEqual(self.default_payload["biosamples"][0]["swab_site"], bs.sample_site)

        self.assertEqual(bs.metadata.count(), 4)
        for record in bs.metadata.all():
            self.assertEqual(str(self.default_payload["biosamples"][0]["metadata"][record.meta_tag][record.meta_name]), record.value) # all metadata is str atm


    def test_biosample_update(self):
        # create a biosample
        self._add_biosample()

        payload = {
            "username": self.user.username,
            "token": self.key.key,
            "biosamples": [
                {
                    "central_sample_id": "HOOT-00001",
                    "root_biosample_source_id": "HOOTER-1",
                    "source_age": 31,
                    "source_sex": "F",
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }
        n_biosamples = models.BiosampleArtifact.objects.count()
        response = self.c.post(reverse('api.artifact.biosample.update'), payload, secure=True, content_type="application/json")
        self.assertEqual(200, response.status_code)

        self.assertEqual(n_biosamples, models.BiosampleArtifact.objects.count())

        bs = models.BiosampleArtifact.objects.get(central_sample_id=self.default_central_sample_id)
        self.assertEqual(payload["biosamples"][0]["central_sample_id"], bs.dice_name)
        self.assertEqual(payload["biosamples"][0]["root_biosample_source_id"], bs.root_biosample_source_id)
        self.assertEqual("M", bs.created.source_sex) # should stay the same
        self.assertEqual(30, bs.created.source_age) # should stay the same

    def test_biosample_add_then_update(self):
        # create a biosample
        self._add_biosample()

        # Now update
        payload = {
            "username": self.user.username,
            "token": self.key.key,
            "biosamples": [
                {
                    "central_sample_id": self.default_central_sample_id,
                    "root_biosample_source_id": "HOOTER-1",
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }
        n_biosamples = models.BiosampleArtifact.objects.count()
        response = self.c.post(reverse('api.artifact.biosample.update'), payload, secure=True, content_type="application/json")
        self.assertEqual(200, response.status_code)

        self.assertEqual(models.BiosampleArtifact.objects.count(), n_biosamples) # should not increase sample count

        bs = models.BiosampleArtifact.objects.get(central_sample_id=self.default_central_sample_id)
        self.assertEqual(payload["biosamples"][0]["central_sample_id"], bs.dice_name)
        self.assertEqual(payload["biosamples"][0]["root_biosample_source_id"], bs.root_biosample_source_id)
