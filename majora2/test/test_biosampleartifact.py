import datetime
import uuid
import copy

from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from majora2 import models
from majora2.test.test_basic_api import BasicAPITest

import sys
import json

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
                    },
                    "metrics": {
                        "ct": {
                            "records": {
                                1: {
                                    "test_platform": "INHOUSE",
                                    "test_target": "S",
                                    "test_kit": "INHOUSE",
                                    "ct_value": 20,
                                },
                                2: {
                                    "test_platform": "INHOUSE",
                                    "test_target": "E",
                                    "test_kit": "INHOUSE",
                                    "ct_value": 21,
                                },
                            }
                        }
                    },
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }

    def _add_biosample(self, payload):
        response = self.c.post(reverse('api.artifact.biosample.add'), payload, secure=True, content_type="application/json")
        self.assertEqual(200, response.status_code)

        j = response.json()
        if j["errors"] != 0:
            sys.stderr.write(json.dumps(j, indent=4, sort_keys=True) + '\n')
        self.assertEqual(0, j["errors"])
        bs = models.BiosampleArtifact.objects.get(central_sample_id=self.default_central_sample_id)
        return bs

    def test_add_biosample(self):
        payload = copy.deepcopy(self.default_payload)

        n_biosamples = models.BiosampleArtifact.objects.count()
        bs = self._add_biosample(payload)
        self.assertEqual(models.BiosampleArtifact.objects.count(), n_biosamples+1)

        self._test_biosample(bs, payload)

    def _test_biosample(self, bs, payload):
        self.assertEqual(payload["biosamples"][0]["adm1"], bs.created.collection_location_adm1)
        self.assertEqual(payload["biosamples"][0]["central_sample_id"], bs.dice_name)

        self.assertEqual(datetime.datetime.strptime(payload["biosamples"][0]["collection_date"], "%Y-%m-%d").date(), bs.created.collection_date)
        self.assertEqual(payload["biosamples"][0]["is_surveillance"], bs.created.coguk_supp.is_surveillance)

        received_date = None
        try:
            received_date = datetime.datetime.strptime(payload["biosamples"][0]["collection_date"], "%Y-%m-%d").date()
        except TypeError:
            pass
        self.assertEqual(received_date, bs.created.received_date)
        self.assertEqual(payload["biosamples"][0]["adm2"].upper(), bs.created.collection_location_adm2) # adm2 co-erced to upper
        self.assertEqual(payload["biosamples"][0]["source_age"], bs.created.source_age)
        self.assertEqual(payload["biosamples"][0]["source_sex"], bs.created.source_sex)

        biosample_sources = []
        for record in bs.created.records.all():
            if record.in_group and record.in_group.kind == "Biosample Source":
                biosample_sources.append(record.in_group.secondary_id)
        self.assertEqual(len(biosample_sources), 1)
        self.assertEqual(payload["biosamples"][0]["biosample_source_id"], biosample_sources[0])

        self.assertEqual(payload["biosamples"][0]["collecting_org"], bs.created.collected_by)
        self.assertEqual(self.user, bs.created.submission_user)
        self.assertEqual(self.user.profile.institute, bs.created.submission_org)
        self.assertEqual(self.user.profile.institute.name, bs.created.submitted_by)

        self.assertEqual(payload["biosamples"][0]["collection_pillar"], bs.created.coguk_supp.collection_pillar)
        self.assertEqual(payload["biosamples"][0]["root_sample_id"], bs.root_sample_id)
        self.assertEqual(payload["biosamples"][0]["sample_type_collected"], bs.sample_type_collected)
        self.assertEqual(payload["biosamples"][0]["sample_type_received"], bs.sample_type_current)
        self.assertEqual(payload["biosamples"][0]["sender_sample_id"], bs.sender_sample_id)
        self.assertEqual(payload["biosamples"][0]["swab_site"], bs.sample_site)

        # Metadata
        self.assertEqual(bs.metadata.count(), 4)
        for record in bs.metadata.all():
            self.assertEqual(str(payload["biosamples"][0]["metadata"][record.meta_tag][record.meta_name]), record.value) # all metadata is str atm

        # Metrics
        n_records = 0
        self.assertEqual(bs.metrics.count(), 1)
        for metric in bs.metrics.all():
            for record in metric.metric_records.all():
                n_records += 1
        self.assertEqual(n_records, 2)

        for i, metric in payload["biosamples"][0]["metrics"]["ct"]["records"].items():
            self.assertIsNotNone(models.TemporaryMajoraArtifactMetricRecord_ThresholdCycle.objects.filter(
                artifact_metric__artifact=bs,
                test_platform = metric["test_platform"],
                test_kit = metric["test_kit"],
                test_target = metric["test_target"],
                ct_value = metric["ct_value"]
            ).first())


    def test_biosample_pha_update(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        self._add_biosample(payload)

        update_payload = {
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
        response = self.c.post(reverse('api.artifact.biosample.update'), update_payload, secure=True, content_type="application/json")
        self.assertEqual(200, response.status_code)

        self.assertEqual(n_biosamples, models.BiosampleArtifact.objects.count())

        bs = models.BiosampleArtifact.objects.get(central_sample_id=self.default_central_sample_id)
        self.assertEqual(update_payload["biosamples"][0]["root_biosample_source_id"], bs.root_biosample_source_id)
        self._test_biosample(bs, payload) # determine nothing has changed from the initial payload

    def test_biosample_update(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        self._add_biosample(payload)

        update_payload = {
            "username": self.user.username,
            "token": self.key.key,
            "biosamples": [
                {
                    "adm1": "UK-WLS",
                    "central_sample_id": self.default_central_sample_id,
                    "collection_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "is_surveillance": True,

                    "received_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "adm2": "Swansea",
                    "source_age": 31,
                    "source_sex": "F",
                    "adm2_private": "SA4",
                    "biosample_source_id": "XYZ12345",
                    "collecting_org": "Parliament of Hooters",
                    "collection_pillar": 2,
                    "root_sample_id": "PHA_67890",
                    "sample_type_collected": "BAL",
                    "sample_type_received": "primary",
                    "sender_sample_id": "LAB67890",
                    "swab_site": "", # None will turn to ""
                    "metadata": {
                        "test": {
                            "bubo": "bubo",
                            "hoots": 8,
                            "hooting": False,

                        },
                        "majora": {
                            "mask": "creepy",
                        }
                    },
                    "metrics": {
                        "ct": {
                            "records": {
                                1: {
                                    "test_platform": "INHOUSE",
                                    "test_target": "S",
                                    "test_kit": "INHOUSE",
                                    "ct_value": 20,
                                },
                                2: {
                                    "test_platform": "INHOUSE",
                                    "test_target": "E",
                                    "test_kit": "INHOUSE",
                                    "ct_value": 21,
                                },
                            }
                        }
                    },
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }
        bs = self._add_biosample(update_payload)

        with self.assertRaises(AssertionError):
            # Check that the biosample has changed from the initial
            self._test_biosample(bs, payload)
        self._test_biosample(bs, update_payload)

    def test_biosample_add_overwrite_metadata(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        bs = self._add_biosample(payload)

        update_payload = copy.deepcopy(self.default_payload)
        update_payload["biosamples"][0]["metadata"]["test"]["hooting"] = True
        update_payload["biosamples"][0]["metadata"]["majora"]["mask"] = "cute"
        bs = self._add_biosample(update_payload)

        with self.assertRaises(AssertionError):
            # Check that the biosample has changed from the initial
            self._test_biosample(bs, payload)
        self._test_biosample(bs, update_payload)

    def test_biosample_add_overwrite_metrics(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        bs = self._add_biosample(payload)

        update_payload = copy.deepcopy(self.default_payload)
        update_payload["biosamples"][0]["metrics"]["ct"]["records"][2]["ct_value"] = 30
        bs = self._add_biosample(update_payload)

        with self.assertRaises(AssertionError):
            # Check that the biosample has changed from the initial
            self._test_biosample(bs, payload)
        self._test_biosample(bs, update_payload)

    def test_biosample_add_update_nostomp(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        bs = self._add_biosample(payload)

        payload = copy.deepcopy(self.default_payload)
        payload["biosamples"][0]["collection_pillar"] = 2

        bs = self._add_biosample(payload)
        self._test_biosample(bs, payload) # compare object to payload

    def test_biosample_add_update_stomp(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        bs = self._add_biosample(payload)

        stomp_payload = {
            "username": self.user.username,
            "token": self.key.key,
            "biosamples": [
                {
                    "adm1": "UK-ENG",
                    "central_sample_id": self.default_central_sample_id,
                    "collection_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "is_surveillance": False,

                    "received_date": None,
                    "adm2": None,
                    "source_age": None,
                    "source_sex": None,
                    "adm2_private": None,
                    "biosample_source_id": None,
                    "collecting_org": None,
                    "collection_pillar": None,
                    "root_sample_id": None,
                    "sample_type_collected": None,
                    "sample_type_received": None,
                    "sender_sample_id": None,
                    "swab_site": None,
                    "metadata": {
                        "test": {
                            "bubo": None,
                            "hoots": None,
                            "hooting": None,

                        },
                        "majora": {
                            "mask": None,
                        }
                    },
                    "metrics": {},
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }
        bs = self._add_biosample(stomp_payload)
        self._test_biosample(bs, stomp_payload) # compare object to payload

