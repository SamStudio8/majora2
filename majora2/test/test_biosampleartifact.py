import datetime
import uuid
import copy

from django.test import Client, TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from majora2 import models
from majora2 import forms
from majora2.test.test_basic_api import BasicAPITest

from tatl import models as tmodels

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
                    "root_sample_id": "PHA_12345",
                    "sample_type_collected": "swab",
                    "sample_type_received": "primary",
                    "sender_sample_id": "LAB12345",
                    "swab_site": "nose-throat",

                    "collection_pillar": 1,
                    "is_hcw": True,
                    "is_hospital_patient": True,
                    "is_icu_patient": False,
                    "admitted_with_covid_diagnosis": True,
                    "employing_hospital_name": "Hoot Point Hospital",
                    "employing_hospital_trust_or_board": "Hoot Point Hospital Trust",
                    "admission_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "admitted_hospital_name": "Hooting Hospital",
                    "admitted_hospital_trust_or_board": "Hooting Hospital Trust",
                    "is_care_home_worker": False,
                    "is_care_home_resident": False,
                    "anonymised_care_home_code": None,

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

    def _add_biosample(self, payload, expected_errors=0, update=False):
        endpoint = "api.artifact.biosample.add"
        if update:
            endpoint = "api.artifact.biosample.update"
        response = self.c.post(reverse(endpoint), payload, secure=True, content_type="application/json")
        self.assertEqual(200, response.status_code)

        j = response.json()
        if j["errors"] != expected_errors:
            sys.stderr.write(json.dumps(j, indent=4, sort_keys=True) + '\n')
        self.assertEqual(expected_errors, j["errors"])

        bs = None
        try:
            bs = models.BiosampleArtifact.objects.get(central_sample_id=self.default_central_sample_id)
        except models.BiosampleArtifact.DoesNotExist:
            pass
        return bs, j

    def test_add_biosample(self):
        payload = copy.deepcopy(self.default_payload)

        n_biosamples = models.BiosampleArtifact.objects.count()
        bs, j = self._add_biosample(payload)
        self.assertEqual(models.BiosampleArtifact.objects.count(), n_biosamples+1)

        self._test_biosample(bs, payload)

    def _test_biosample(self, bs, payload):

        # Fixed values
        self.assertEqual("United Kingdom", bs.created.collection_location_country)
        self.assertEqual("2697049", bs.taxonomy_identifier)


        self.assertEqual(payload["biosamples"][0].get("adm1"), bs.created.collection_location_adm1)
        self.assertEqual(payload["biosamples"][0]["central_sample_id"], bs.dice_name)
        self.assertEqual(datetime.datetime.strptime(payload["biosamples"][0]["collection_date"], "%Y-%m-%d").date(), bs.created.collection_date)

        if hasattr(bs.created, "coguk_supp"):
            self.assertEqual(payload["biosamples"][0].get("is_surveillance"), bs.created.coguk_supp.is_surveillance)
            self.assertEqual(payload["biosamples"][0].get("collection_pillar"), bs.created.coguk_supp.collection_pillar)
            self.assertEqual(payload["biosamples"][0].get("is_hcw"), bs.created.coguk_supp.is_hcw)
            self.assertEqual(payload["biosamples"][0].get("is_hospital_patient"), bs.created.coguk_supp.is_hospital_patient)
            self.assertEqual(payload["biosamples"][0].get("is_icu_patient"), bs.created.coguk_supp.is_icu_patient)
            self.assertEqual(payload["biosamples"][0].get("admitted_with_covid_diagnosis"), bs.created.coguk_supp.admitted_with_covid_diagnosis)
            self.assertEqual(payload["biosamples"][0].get("employing_hospital_name"), bs.created.coguk_supp.employing_hospital_name)
            self.assertEqual(payload["biosamples"][0].get("employing_hospital_trust_or_board"), bs.created.coguk_supp.employing_hospital_trust_or_board)

            admission_date = None
            try:
                admission_date = datetime.datetime.strptime(payload["biosamples"][0].get("admission_date"), "%Y-%m-%d").date()
            except TypeError:
                pass
            self.assertEqual(admission_date, bs.created.coguk_supp.admission_date)

            self.assertEqual(payload["biosamples"][0].get("admitted_hospital_name"), bs.created.coguk_supp.admitted_hospital_name)
            self.assertEqual(payload["biosamples"][0].get("admitted_hospital_trust_or_board"), bs.created.coguk_supp.admitted_hospital_trust_or_board)
            self.assertEqual(payload["biosamples"][0].get("is_care_home_worker"), bs.created.coguk_supp.is_care_home_worker)
            self.assertEqual(payload["biosamples"][0].get("is_care_home_resident"), bs.created.coguk_supp.is_care_home_resident)
            self.assertEqual(payload["biosamples"][0].get("anonymised_care_home_code"), bs.created.coguk_supp.anonymised_care_home_code)

        received_date = None
        try:
            received_date = datetime.datetime.strptime(payload["biosamples"][0].get("received_date"), "%Y-%m-%d").date()
        except TypeError:
            pass
        self.assertEqual(received_date, bs.created.received_date)

        adm2 = None
        try:
            adm2 = payload["biosamples"][0].get("adm2").upper() #adm2 coerced to upper
        except AttributeError:
            pass
        self.assertEqual(adm2, bs.created.collection_location_adm2)
        self.assertEqual(payload["biosamples"][0].get("source_age"), bs.created.source_age)
        self.assertEqual(payload["biosamples"][0].get("source_sex", ""), bs.created.source_sex)
        self.assertEqual(payload["biosamples"][0].get("adm2_private"), bs.created.private_collection_location_adm2)

        biosample_sources = []
        for record in bs.created.records.all():
            if record.in_group and record.in_group.kind == "Biosample Source":
                biosample_sources.append(record.in_group.secondary_id)

        if payload["biosamples"][0].get("biosample_source_id"):
            self.assertEqual(payload["biosamples"][0]["biosample_source_id"], biosample_sources[0])
            self.assertEqual(payload["biosamples"][0]["biosample_source_id"], bs.primary_group.dice_name)
            self.assertEqual(len(biosample_sources), 1)
        else:
            self.assertEqual(len(biosample_sources), 0)
            self.assertEqual(None, bs.primary_group)

        self.assertEqual(payload["biosamples"][0].get("collecting_org"), bs.created.collected_by)
        self.assertEqual(self.user, bs.created.submission_user)
        self.assertEqual(self.user.profile.institute.name, bs.created.submitted_by)
        self.assertEqual(self.user.profile.institute, bs.created.submission_org)

        self.assertEqual(payload["biosamples"][0].get("root_sample_id"), bs.root_sample_id)
        self.assertEqual(payload["biosamples"][0].get("sample_type_collected", ""), bs.sample_type_collected)
        self.assertEqual(payload["biosamples"][0].get("sample_type_received"), bs.sample_type_current)
        self.assertEqual(payload["biosamples"][0].get("sender_sample_id"), bs.sender_sample_id)
        self.assertEqual(payload["biosamples"][0].get("swab_site"), bs.sample_site)

        # Metadata
        expected_n_metadata = 0
        for tag_name, tag_data in payload["biosamples"][0]["metadata"].items():
            expected_n_metadata += len(tag_data.keys())

        self.assertEqual(bs.metadata.count(), expected_n_metadata)
        record_tests = 0
        for record in bs.metadata.all():
            self.assertEqual(str(payload["biosamples"][0]["metadata"][record.meta_tag][record.meta_name]), record.value) # all metadata is str atm
            record_tests += 1
        self.assertEqual(record_tests, expected_n_metadata)

        # Metrics
        expected_n_metrics_objects = 0
        expected_n_metrics_records = 0
        for tag_name, tag_data in payload["biosamples"][0]["metrics"].items():
            expected_n_metrics_objects += 1
            expected_n_metrics_records += len(tag_data["records"])

        n_records = 0
        self.assertEqual(bs.metrics.count(), expected_n_metrics_objects)
        for metric in bs.metrics.all():
            for record in metric.metric_records.all():
                n_records += 1
        self.assertEqual(n_records, expected_n_metrics_records)

        record_tests = 0
        if expected_n_metrics_objects > 0:
            for i, metric in payload["biosamples"][0]["metrics"]["ct"]["records"].items():
                self.assertIsNotNone(models.TemporaryMajoraArtifactMetricRecord_ThresholdCycle.objects.filter(
                    artifact_metric__artifact=bs,
                    test_platform = metric["test_platform"],
                    test_kit = metric["test_kit"],
                    test_target = metric["test_target"],
                    ct_value = metric["ct_value"]
                ).first())
                record_tests += 1
        self.assertEqual(record_tests, expected_n_metrics_records)


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
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }
        self._add_biosample(update_payload, update=True)

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
                    "root_sample_id": "PHA_67890",
                    "sample_type_collected": "BAL",
                    "sample_type_received": "primary",
                    "sender_sample_id": "LAB67890",
                    "swab_site": None,

                    "collection_pillar": 2,
                    "is_hcw": False,
                    "is_hospital_patient": True,
                    "is_icu_patient": True,
                    "admitted_with_covid_diagnosis": False,
                    "employing_hospital_name": None,
                    "employing_hospital_trust_or_board": None,
                    "admission_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "admitted_hospital_name": "HOSPITAL",
                    "admitted_hospital_trust_or_board": "HOSPITAL",
                    "is_care_home_worker": True,
                    "is_care_home_resident": True,
                    "anonymised_care_home_code": "CC-X00",

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
        bs, j = self._add_biosample(update_payload)

        with self.assertRaises(AssertionError):
            # Check that the biosample has changed from the initial
            self._test_biosample(bs, payload)
        self._test_biosample(bs, update_payload)

        # Check the supp has been updated and not recreated
        self.assertEqual(models.COGUK_BiosourceSamplingProcessSupplement.objects.count(), 1)

    def test_biosample_add_overwrite_metadata(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        bs, j = self._add_biosample(payload)

        update_payload = copy.deepcopy(self.default_payload)
        update_payload["biosamples"][0]["metadata"]["test"]["hooting"] = True
        update_payload["biosamples"][0]["metadata"]["majora"]["mask"] = "cute"
        update_payload["biosamples"][0]["metrics"] = {}
        bs, j = self._add_biosample(update_payload)

        with self.assertRaises(AssertionError):
            # Check that the biosample has changed from the initial
            self._test_biosample(bs, payload)

        update_payload["biosamples"][0]["metrics"] = payload["biosamples"][0]["metrics"] # reinsert to check metrics have stayed
        self._test_biosample(bs, update_payload)

        # Check tatl
        expected_context = {
            "changed_fields": [],
            "nulled_fields": [],
            "changed_metadata": ["metadata:test.hooting", "metadata:majora.mask"],
            "flashed_metrics": [],
        }
        self._test_update_biosample_tatl(j["request"], expected_context)

    def test_biosample_add_overwrite_metrics(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        bs, j = self._add_biosample(payload)

        update_payload = copy.deepcopy(self.default_payload)
        update_payload["biosamples"][0]["metrics"]["ct"]["records"][2]["ct_value"] = 30
        bs, j = self._add_biosample(update_payload)

        with self.assertRaises(AssertionError):
            # Check that the biosample has changed from the initial
            self._test_biosample(bs, payload)
        self._test_biosample(bs, update_payload)

        # Check tatl
        expected_context = {
            "changed_fields": [],
            "nulled_fields": [],
            "changed_metadata": [],
            "flashed_metrics": ["ct"],
        }
        self._test_update_biosample_tatl(j["request"], expected_context)

    def test_biosample_add_update_nostomp(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        bs, j = self._add_biosample(payload)

        payload = copy.deepcopy(self.default_payload)
        payload["biosamples"][0]["collection_pillar"] = 2

        bs, j = self._add_biosample(payload)
        self._test_biosample(bs, payload) # compare object to payload

    def test_biosample_add_update_nuke_stomp(self):
        #NOTE Some fields become "" empty string when sending None
        #TODO   it would be nice if that behaviour was consistent

        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        bs, j = self._add_biosample(payload)

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
                    "source_sex": "",
                    "adm2_private": None,
                    "biosample_source_id": "ABC12345", # can't nuke biosample_source_id once it has been set
                    "collecting_org": None,
                    "root_sample_id": None,
                    "sample_type_collected": "",
                    "sample_type_received": None,
                    "sender_sample_id": None,
                    "swab_site": None,

                    "collection_pillar": None,
                    "is_hcw": None,
                    "is_hospital_patient": None,
                    "is_icu_patient": None,
                    "admitted_with_covid_diagnosis": None,
                    "employing_hospital_name": None,
                    "employing_hospital_trust_or_board": None,
                    "admission_date": None,
                    "admitted_hospital_name": None,
                    "admitted_hospital_trust_or_board": None,
                    "is_care_home_worker": None,
                    "is_care_home_resident": None,
                    "anonymised_care_home_code": None,
                    "metadata": {},
                    "metrics": {},
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }
        bs, j = self._add_biosample(stomp_payload)

        # Add the metadata and metrics back to show that blanking them does nothing
        stomp_payload["biosamples"][0]["metadata"] = payload["biosamples"][0]["metadata"]
        stomp_payload["biosamples"][0]["metrics"] = payload["biosamples"][0]["metrics"]
        self._test_biosample(bs, stomp_payload) # compare object to payload

        # Check the supp has been updated and not recreated
        self.assertEqual(models.COGUK_BiosourceSamplingProcessSupplement.objects.count(), 1)


    def test_biosample_minimal_add_metrics_update(self):
        # Add a minimal biosample and update it with some metrics
        payload = {
            "username": self.user.username,
            "token": self.key.key,
            "biosamples": [
                {
                    "adm1": "UK-ENG",
                    "central_sample_id": self.default_central_sample_id,
                    "collection_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "is_surveillance": False,
                    "is_hcw": True,
                    "metadata": {},
                    "metrics": {},
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }
        bs, j = self._add_biosample(payload)
        self._test_biosample(bs, payload)

        new_payload = {
            "username": self.user.username,
            "token": self.key.key,
            "biosamples": [
                {
                    "central_sample_id": self.default_central_sample_id,
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
        }
        bs, j = self._add_biosample(new_payload, update=True)

        update_payload = copy.deepcopy(payload)
        update_payload["biosamples"][0]["metadata"] = new_payload["biosamples"][0]["metadata"]
        update_payload["biosamples"][0]["metrics"] = new_payload["biosamples"][0]["metrics"]
        self._test_biosample(bs, update_payload)

    def test_biosample_full_add_partial_update(self):
        # Add a full biosample and update a few additional fields that were placeholded
        payload = copy.deepcopy(self.default_payload)
        bs, j = self._add_biosample(payload)
        self._test_biosample(bs, payload)

        payload["biosamples"][0]["is_surveillance"] = True
        payload["biosamples"][0]["collection_pillar"] = 2
        bs, j = self._add_biosample(payload, update=True)
        self._test_biosample(bs, payload)

    def test_biosample_minimal_add_partial_update(self):
        # Add a minimal biosample and update a few additional fields
        payload = {
            "username": self.user.username,
            "token": self.key.key,
            "biosamples": [
                {
                    "adm1": "UK-ENG",
                    "central_sample_id": self.default_central_sample_id,
                    "collection_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "is_surveillance": False,
                    "is_hcw": True,
                    "metadata": {},
                    "metrics": {},
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }
        bs, j = self._add_biosample(payload)
        self._test_biosample(bs, payload)

        new_payload = copy.deepcopy(payload)
        del new_payload["biosamples"][0]["adm1"]
        del new_payload["biosamples"][0]["collection_date"]

        new_payload["biosamples"][0]["is_surveillance"] = True
        payload["biosamples"][0]["is_surveillance"] = True

        new_payload["biosamples"][0]["collection_pillar"] = 2
        payload["biosamples"][0]["collection_pillar"] = 2

        with self.assertRaises(AssertionError):
            # Check that the biosample has changed from the last
            self._test_biosample(bs, payload)

        bs, j = self._add_biosample(new_payload, update=True)
        self._test_biosample(bs, payload)


    def test_biosample_full_add_single_update(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        payload["biosamples"][0]["metrics"] = {} # ignore metrics
        bs, j = self._add_biosample(payload)

        del payload["biosamples"][0]["is_hcw"]
        del payload["biosamples"][0]["is_hospital_patient"]
        del payload["biosamples"][0]["is_icu_patient"]
        del payload["biosamples"][0]["admitted_with_covid_diagnosis"]
        del payload["biosamples"][0]["employing_hospital_name"]
        del payload["biosamples"][0]["employing_hospital_trust_or_board"]
        del payload["biosamples"][0]["admission_date"]
        del payload["biosamples"][0]["admitted_hospital_name"]
        del payload["biosamples"][0]["admitted_hospital_trust_or_board"]
        del payload["biosamples"][0]["is_care_home_worker"]
        del payload["biosamples"][0]["is_care_home_resident"]
        del payload["biosamples"][0]["anonymised_care_home_code"]

        del payload["biosamples"][0]["collection_date"]
        del payload["biosamples"][0]["received_date"]
        del payload["biosamples"][0]["source_age"]
        del payload["biosamples"][0]["source_sex"]
        del payload["biosamples"][0]["adm1"]
        del payload["biosamples"][0]["adm2"]
        del payload["biosamples"][0]["adm2_private"]
        del payload["biosamples"][0]["collecting_org"]

        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        partial_fields = {
            "collection_date": yesterday,
            "received_date": yesterday,
            "source_age": 29,
            "source_sex": "F",
            "adm1": "UK-WLS",
            "adm2": "SWANSEA",
            "adm2_private": "SA4",
            "collecting_org": "Hooting High Hospital",

            "is_hcw": False,
            "is_hospital_patient": False,
            "is_icu_patient": True,
            "admitted_with_covid_diagnosis": False,
            "employing_hospital_name": "HOSPITAL",
            "employing_hospital_trust_or_board": "HOSPITAL",
            "admission_date": None,
            "admitted_hospital_name": "HOSPITAL",
            "admitted_hospital_trust_or_board": "HOSPITAL",
            "is_care_home_worker": True,
            "is_care_home_resident": True,
            "anonymised_care_home_code": "CC-X00",
        }
        check_payload = copy.deepcopy(self.default_payload)
        check_payload["biosamples"][0]["metrics"] = {} # ignore metrics
        for k, v in partial_fields.items():
            update_payload = copy.deepcopy(payload)
            update_payload["biosamples"][0][k] = v

            bs, j = self._add_biosample(update_payload, update=True)

            with self.assertRaises(AssertionError):
                # Check that the biosample has changed from the last
                self._test_biosample(bs, check_payload)

            check_payload["biosamples"][0][k] = v
            self._test_biosample(bs, check_payload) # compare object to payload

            # Check tatl
            expected_context = {
                "changed_fields": [],
                "nulled_fields": [],
                "changed_metadata": [],
                "flashed_metrics": [],
            }
            if v is None:
                expected_context["nulled_fields"].append(k)
            else:
                expected_context["changed_fields"].append(k)
            self._test_update_biosample_tatl(j["request"], expected_context)


    def test_reject_partial_new_biosampleartifact(self):
        payload = {
            "username": self.user.username,
            "token": self.key.key,
            "biosamples": [
                {
                    "adm1": "UK-ENG",
                    "central_sample_id": self.default_central_sample_id,
                    "collection_date": datetime.date.today().strftime("%Y-%m-%d"),
                    "is_surveillance": False,
                    "is_hcw": True,
                    "metadata": {},
                    "metrics": {},
                },
            ],
            "client_name": "pytest",
            "client_version": 1,
        }
        bs, j = self._add_biosample(payload, expected_errors=1, update=True)
        self.assertIsNone(bs)
        self.assertIn("Cannot use `partial` on new BiosampleArtifact %s" % self.default_central_sample_id, j["messages"])


    def test_add_biosample_tatl(self):
        payload = copy.deepcopy(self.default_payload)
        bs, j = self._add_biosample(payload)

        tatl = tmodels.TatlRequest.objects.filter(response_uuid=j["request"]).first()
        self.assertIsNotNone(tatl)

        self.assertEqual(tatl.verbs.count(), 2)

        expected_verbs = [
            ("CREATE", models.BiosampleArtifact.objects.get(dice_name=self.default_central_sample_id)),
            ("CREATE", models.BiosampleSource.objects.get(dice_name="ABC12345")),
        ]

        for verb in tatl.verbs.all():
            self.assertIn( (verb.verb, verb.content_object), expected_verbs )

    def _test_update_biosample_tatl(self, request_id, expected_context):
        tatl = tmodels.TatlRequest.objects.filter(response_uuid=request_id).first()
        self.assertIsNotNone(tatl)

        self.assertEqual(tatl.verbs.count(), 1)

        expected_verbs = [
            ("UPDATE", models.BiosampleArtifact.objects.get(dice_name=self.default_central_sample_id)),
        ]
        verb = tatl.verbs.all()[0]
        extra_j = json.loads(verb.extra_context)

        self.assertIn("changed_fields", extra_j)
        self.assertIn("nulled_fields", extra_j)
        self.assertIn("changed_metadata", extra_j)
        self.assertIn("flashed_metrics", extra_j)

        self.assertEqual(len(extra_j["changed_fields"]), len(expected_context["changed_fields"]))
        self.assertEqual(len(extra_j["nulled_fields"]), len(expected_context["nulled_fields"]))
        self.assertEqual(len(extra_j["changed_metadata"]), len(expected_context["changed_metadata"]))
        self.assertEqual(len(extra_j["flashed_metrics"]), len(expected_context["flashed_metrics"]))

        # Use modelform classmethod to resolve the correct mapping
        # Cheat and convert the list to a dict so it works as a payload
        for cat in expected_context:
            d = {}
            for k in expected_context[cat]:
                d[k] = None

            d = forms.BiosampleArtifactModelForm.map_request_fields(d)
            d = forms.BiosourceSamplingProcessModelForm.map_request_fields(d) # pass through each form used by the interface

            for f in d:
                self.assertIn(f, extra_j[cat])


    # Test nuke metadata (with new None)
    # Test nuke ct (currently only nuked on new)
    # Test mod preform
    # Test initial data is stompy
