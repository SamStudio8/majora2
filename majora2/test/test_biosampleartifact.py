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
                    "adm2": "BIRMINGHAM",
                    "central_sample_id": self.default_central_sample_id,
                    "collection_date": "2020-08-24",
                    "is_surveillance": False,
                    "source_age": 30,
                    "source_sex": "M",
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }

    def _add_biosample(self):
        response = self.c.post(reverse('api.artifact.biosample.add'), self.default_payload, secure=True, content_type="application/json")
        self.assertEqual(200, response.status_code)
        bs = models.BiosampleArtifact.objects.get(central_sample_id=self.default_central_sample_id)
        return bs

    def test_biosample_add(self):
        n_biosamples = models.BiosampleArtifact.objects.count()
        bs = self._add_biosample()
        self.assertEqual(models.BiosampleArtifact.objects.count(), n_biosamples+1)

        self.assertEqual(self.default_payload["biosamples"][0]["central_sample_id"], bs.dice_name)
        self.assertEqual(self.default_payload["biosamples"][0]["source_sex"], bs.created.source_sex)
        self.assertEqual(self.default_payload["biosamples"][0]["source_age"], bs.created.source_age)

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
