import datetime
import json
import uuid

from django.contrib.auth.models import User, Permission
from django.urls import reverse
from django.utils import timezone

from majora2 import models
from tatl import models as tmodels

from majora2.test.test_basic_api import OAuthAPIClientBase


class OAuthTaskTest(OAuthAPIClientBase):
    def setUp(self):
        super().setUp()

        self.endpoint = reverse("api.majora.task.get")
        self.scope = "" # scopeless
        self.token = self._get_token(self.scope)

        # Add a task
        self.user_task_id = uuid.uuid4()
        ttask = tmodels.TatlTask(
            celery_uuid = self.user_task_id,
            task = "my-task",
            payload = json.dumps({}),
            timestamp = timezone.now(),
            request = None,
            user = self.user,
        )
        ttask.save()

        # Add another task owned by someone else
        self.not_user_task_id = uuid.uuid4()
        ttask = tmodels.TatlTask(
            celery_uuid = self.not_user_task_id,
            task = "my-other-task",
            payload = json.dumps({}),
            timestamp = timezone.now(),
            request = None,
            user = self.not_user,
        )
        ttask.save()

    def test_missing_task_id(self):
        payload = {
            "username": "oauth",
            "token": "oauth",
        }
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)
        j = response.json()
        self.assertEqual(j["errors"], 1)
        self.assertIn("'task_id' key missing or empty", "".join(j["messages"]))

    def test_unknown_task_id(self):
        unknown_id = uuid.uuid4()
        payload = {
            "username": "oauth",
            "token": "oauth",
            "task_id": unknown_id,
        }
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)
        j = response.json()
        self.assertEqual(j["errors"], 1)
        self.assertEqual(j["task"]["id"], str(unknown_id))
        self.assertEqual(j["task"]["state"], "DOES_NOT_EXIST")

    def test_user_can_access_their_task_ok(self):
        payload = {
            "task_id": self.user_task_id,
            "username": "oauth",
            "token": "oauth",
        }
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["errors"], 0)

        self.assertEqual(j["task"]["id"], str(self.user_task_id))
        self.assertEqual(j["task"]["state"], "PENDING") # NOTE Test checks the owner guard, not the celery result which is PENDING for unknown tasks

    def test_user_cannot_access_other_task(self):
        payload = {
            "task_id": self.not_user_task_id,
            "username": "oauth",
            "token": "oauth",
        }
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["errors"], 1)

        self.assertEqual(j["task"]["id"], str(self.not_user_task_id))
        self.assertEqual(j["task"]["state"], "PERMISSION_DENIED")
