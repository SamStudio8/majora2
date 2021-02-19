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
        if hasattr(bs.created, "coguk_supp"):
            self.assertEqual(payload["biosamples"][0]["is_surveillance"], bs.created.coguk_supp.is_surveillance)
            self.assertEqual(payload["biosamples"][0]["collection_pillar"], bs.created.coguk_supp.collection_pillar)
            self.assertEqual(payload["biosamples"][0]["is_hcw"], bs.created.coguk_supp.is_hcw)
            self.assertEqual(payload["biosamples"][0]["is_hospital_patient"], bs.created.coguk_supp.is_hospital_patient)
            self.assertEqual(payload["biosamples"][0]["is_icu_patient"], bs.created.coguk_supp.is_icu_patient)
            self.assertEqual(payload["biosamples"][0]["admitted_with_covid_diagnosis"], bs.created.coguk_supp.admitted_with_covid_diagnosis)
            self.assertEqual(payload["biosamples"][0]["employing_hospital_name"], bs.created.coguk_supp.employing_hospital_name)
            self.assertEqual(payload["biosamples"][0]["employing_hospital_trust_or_board"], bs.created.coguk_supp.employing_hospital_trust_or_board)

            admission_date = None
            try:
                admission_date = datetime.datetime.strptime(payload["biosamples"][0]["admission_date"], "%Y-%m-%d").date()
            except TypeError:
                pass
            self.assertEqual(admission_date, bs.created.coguk_supp.admission_date)

            self.assertEqual(payload["biosamples"][0]["admitted_hospital_name"], bs.created.coguk_supp.admitted_hospital_name)
            self.assertEqual(payload["biosamples"][0]["admitted_hospital_trust_or_board"], bs.created.coguk_supp.admitted_hospital_trust_or_board)
            self.assertEqual(payload["biosamples"][0]["is_care_home_worker"], bs.created.coguk_supp.is_care_home_worker)
            self.assertEqual(payload["biosamples"][0]["is_care_home_resident"], bs.created.coguk_supp.is_care_home_resident)
            self.assertEqual(payload["biosamples"][0]["anonymised_care_home_code"], bs.created.coguk_supp.anonymised_care_home_code)

        received_date = None
        try:
            received_date = datetime.datetime.strptime(payload["biosamples"][0]["received_date"], "%Y-%m-%d").date()
        except TypeError:
            pass
        self.assertEqual(received_date, bs.created.received_date)

        adm2 = None # None to ""
        try:
            adm2 = payload["biosamples"][0]["adm2"].upper() #adm2 coerced to upper
        except AttributeError:
            pass
        self.assertEqual(adm2, bs.created.collection_location_adm2)
        self.assertEqual(payload["biosamples"][0]["source_age"], bs.created.source_age)
        self.assertEqual(payload["biosamples"][0]["source_sex"], bs.created.source_sex)
        self.assertEqual(payload["biosamples"][0]["adm2_private"], bs.created.private_collection_location_adm2)

        biosample_sources = []
        for record in bs.created.records.all():
            if record.in_group and record.in_group.kind == "Biosample Source":
                biosample_sources.append(record.in_group.secondary_id)
        self.assertEqual(len(biosample_sources), 1)
        self.assertEqual(payload["biosamples"][0]["biosample_source_id"], biosample_sources[0])

        self.assertEqual(payload["biosamples"][0]["collecting_org"], bs.created.collected_by)
        self.assertEqual(self.user, bs.created.submission_user)
        self.assertEqual(self.user.profile.institute.name, bs.created.submitted_by)
        self.assertEqual(self.user.profile.institute, bs.created.submission_org)

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
                    "root_sample_id": "PHA_67890",
                    "sample_type_collected": "BAL",
                    "sample_type_received": "primary",
                    "sender_sample_id": "LAB67890",
                    "swab_site": "", # None will turn to ""

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
        bs = self._add_biosample(update_payload)

        with self.assertRaises(AssertionError):
            # Check that the biosample has changed from the initial
            self._test_biosample(bs, payload)
        self._test_biosample(bs, update_payload)

        # Check the supp has been updated and not recreated
        self.assertEqual(models.COGUK_BiosourceSamplingProcessSupplement.objects.count(), 1)

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

    def test_biosample_add_update_nuke_stomp(self):
        #NOTE Some fields become "" empty string when sending None
        #TODO   it would be nice if that behaviour was consistent

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
                    "source_sex": "",
                    "adm2_private": None,
                    "biosample_source_id": "ABC12345", # can't nuke biosample_source_id once it has been set
                    "collecting_org": None,
                    "root_sample_id": "",
                    "sample_type_collected": "",
                    "sample_type_received": "",
                    "sender_sample_id": "",
                    "swab_site": "",

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
        bs = self._add_biosample(stomp_payload)

        # Add the metadata and metrics back to show that blanking them does nothing
        stomp_payload["biosamples"][0]["metadata"] = payload["biosamples"][0]["metadata"]
        stomp_payload["biosamples"][0]["metrics"] = payload["biosamples"][0]["metrics"]
        self._test_biosample(bs, stomp_payload) # compare object to payload

        # Check the supp has been updated and not recreated
        self.assertEqual(models.COGUK_BiosourceSamplingProcessSupplement.objects.count(), 1)

    def test_biosample_add_update_partial_supp_stomp(self):
        # create a biosample
        payload = copy.deepcopy(self.default_payload)
        bs = self._add_biosample(payload)

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

        #del payload["biosamples"][0]["collection_date"]
        del payload["biosamples"][0]["received_date"]
        del payload["biosamples"][0]["source_age"]
        del payload["biosamples"][0]["source_sex"]
        del payload["biosamples"][0]["adm1"]
        del payload["biosamples"][0]["adm2"]
        del payload["biosamples"][0]["adm2_private"]
        del payload["biosamples"][0]["collecting_org"]

        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        partial_fields = {
            #"collection_date": yesterday,
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
        for k, v in partial_fields.items():
            update_payload = copy.deepcopy(payload)
            update_payload["biosamples"][0][k] = v

            bs = self._add_biosample(update_payload)

            with self.assertRaises(AssertionError):
                # Check that the biosample has changed from the last
                self._test_biosample(bs, check_payload)

            check_payload["biosamples"][0][k] = v
            self._test_biosample(bs, check_payload) # compare object to payload

    # Test nuke metadata (with new None)
    # Test nuke ct (currently only nuked on new)
    # Test mod preform
