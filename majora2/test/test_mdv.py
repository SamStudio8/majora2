import datetime
import json
import uuid

from django.contrib.auth.models import User, Permission
from django.urls import reverse
from django.utils import timezone

from majora2 import models
from majora2 import mdv_tasks
from tatl import models as tmodels

from majora2.test.test_basic_api import OAuthAPIClientBase

class MdvPhe1Test(OAuthAPIClientBase):
    def setUp(self):
        super().setUp()

        # Agreement
        self.agreement = models.ProfileAgreementDefinition(
            slug="eng-sendersampleid-phe-1",
            proposal_timestamp=timezone.now(),
        )
        self.agreement.save()

        # Biosamples
        for sample in [
            {"name": "eng-secret-opted", "adm1": "UK-ENG", "secret": "yes-secret1", "collection_date": "2022-03-05"},
            {"name": "eng-nosecret-opted", "adm1": "UK-ENG", "secret": None, "received_date": "2022-03-06"},
            {"name": "eng-secret-noopted", "adm1": "UK-ENG", "secret": "suppressed-no-opted-secret3", "user": self.not_user},
            {"name": "wls-secret-opted", "adm1": "UK-WLS", "secret": "suppressed-no-noeng-secret5"},
            {"name": "da1-secret-opted", "adm1": None, "secret": "suppressed-no-noeng-secret6"},
        ]:
            sample_p = models.BiosourceSamplingProcess(
                collection_location_adm1=sample["adm1"],
                who=sample["user"] if sample.get("user") else self.user,
                collection_date=sample["collection_date"] if sample.get("collection_date") else None,
                received_date=sample["received_date"] if sample.get("received_date") else None,
            )
            sample_p.save()

            sample = models.BiosampleArtifact(dice_name=sample["name"], central_sample_id=sample["name"], sender_sample_id=sample["secret"])
            sample.created = sample_p
            sample.save()


    def _sign_for_user(self):
        # Sign for user
        models.ProfileAgreement(
            agreement=self.agreement,
            profile=self.user.profile,
            signature_timestamp=timezone.now()
        ).save()

    def test_no_signatures_has_no_results(self):
        # Nobody has signed so result should be empty
        self.assertTrue(models.BiosampleArtifact.objects.count() > 0)
        result = mdv_tasks.subtask_get_mdv_v3_phe1_faster()
        self.assertEqual(len(result), 0)


    def test_user_has_signed_reveals_applicable_secrets_basic(self):
        self._sign_for_user()

        result = mdv_tasks.subtask_get_mdv_v3_phe1_faster()
        self.assertEqual(len(result), 2)

        str_result = str(result)
        for expected_sample in ["eng-secret-opted", "eng-nosecret-opted"]:
            self.assertIn(expected_sample, str_result)
        self.assertNotIn("suppressed", str_result)


    def test_user_has_signed_reveals_applicable_secrets_detail(self):
        self._sign_for_user()

        result = mdv_tasks.subtask_get_mdv_v3_phe1_faster()
        self.assertEqual(len(result), 2)

        self.assertIn(
            {
                "central_sample_id": "eng-secret-opted",
                "sender_sample_id": "yes-secret1",
                "created": {
                    "adm1": "UK-ENG",
                    "collection_date": "2022-03-05",
                    "received_date": None,
                    "process_model": "BiosourceSamplingProcess"
                }
            },
            result
        )
        self.assertIn(
            {
                "central_sample_id": "eng-nosecret-opted",
                "sender_sample_id": None,
                "created": {
                    "adm1": "UK-ENG",
                    "collection_date": None,
                    "received_date": "2022-03-06",
                    "process_model": "BiosourceSamplingProcess"
                }
            },
            result
        )

    def test_user_signature_revoked_removes_secrets(self):
        self.assertTrue(models.BiosampleArtifact.objects.count() > 0)
        models.ProfileAgreement(
            agreement=self.agreement,
            profile=self.user.profile,
            signature_timestamp=timezone.now(),
            is_terminated=True,
        ).save()
        result = mdv_tasks.subtask_get_mdv_v3_phe1_faster()
        self.assertEqual(len(result), 0)

