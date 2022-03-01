import datetime

from django.urls import reverse

from majora2 import models
from tatl import models as tmodels
from majora2.test.test_basic_api import OAuthAPIClientBase

class OAuthLibraryArtifactTest(OAuthAPIClientBase):
    def setUp(self):
        super().setUp()

        self.endpoint = reverse("api.process.sequencing.add")
        self.scope = "majora2.change_libraryartifact majora2.add_dnasequencingprocess majora2.change_dnasequencingprocess"
        self.token = self._get_token(self.scope)

        # Library needs to exist to add a sequencing run
        self.library_name = "HOOT-LIBRARY-20220125"
        library_o = models.LibraryArtifact(dice_name=self.library_name)
        library_o.save()

    def test_add_basic_sequencing_ok(self):
        process_count = models.DNASequencingProcess.objects.count()

        run_name = "YYMMDD_AB000000_1234_ABCDEFGHI0"
        payload = {
            "library_name": self.library_name,
            "runs": [
                {
                    "bioinfo_pipe_name": "ARTIC Pipeline (iVar)",
                    "bioinfo_pipe_version": "1.3.0",
                    "end_time": "2022-01-25 15:00",
                    "flowcell_id": "ABCDEF",
                    "flowcell_type": "v3",
                    "instrument_make": "ILLUMINA",
                    "instrument_model": "MiSeq",
                    "run_name": run_name,
                    "start_time": "2022-01-25 05:00"
                }
            ],
            "token": "oauth",
            "username": "oauth"
        }

        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["errors"], 0)

        self.assertEqual(models.DNASequencingProcess.objects.count(), process_count + 1)
        assert models.DNASequencingProcess.objects.filter(run_name=run_name).count() == 1

        process = models.DNASequencingProcess.objects.get(run_name=run_name)
        assert process.instrument_make == payload["runs"][0]["instrument_make"]
        assert process.instrument_model == payload["runs"][0]["instrument_model"]
        assert process.flowcell_type == payload["runs"][0]["flowcell_type"]
        assert process.flowcell_id == payload["runs"][0]["flowcell_id"]
        assert process.start_time.strftime("%Y-%m-%d %H:%M") == payload["runs"][0]["start_time"]
        assert process.end_time.strftime("%Y-%m-%d %H:%M") == payload["runs"][0]["end_time"]

        #TODO Should probably also check the other dummy files are created but whatever
        # Check the downstream ABP is created automatically for a new sequencing run
        assert models.AbstractBioinformaticsProcess.objects.filter(
                pipe_kind="Pipeline",
                hook_name="bioinfo-%s" % run_name,
                pipe_name=payload["runs"][0]["bioinfo_pipe_name"],
                pipe_version=payload["runs"][0]["bioinfo_pipe_version"],
        ).count() == 1

        # Check the sequencing process record
        assert models.DNASequencingProcessRecord.objects.filter(
                unique_name="%s-%s" % (run_name, self.library_name)
        ).count() == 1


    def test_m70_add_sequencing_with_future_start_rejected(self):
        run_name = "YYMMDD_AB000000_1234_ABCDEFGHI0"
        start_time = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        end_time = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        payload = {
            "library_name": self.library_name,
            "runs": [
                {
                    "bioinfo_pipe_name": "ARTIC Pipeline (iVar)",
                    "bioinfo_pipe_version": "1.3.0",
                    "end_time": end_time,
                    "flowcell_id": "ABCDEF",
                    "flowcell_type": "v3",
                    "instrument_make": "ILLUMINA",
                    "instrument_model": "MiSeq",
                    "run_name": run_name,
                    "start_time": start_time
                }
            ],
            "token": "oauth",
            "username": "oauth"
        }

        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["errors"], 1) # only one error is emitted for a bad form, but check both errors are emitted below

        message_strs = []
        for message in j["messages"]:
            for k, v in message.items():
                message_strs.extend([x.get("message") for x in v])

        self.assertIn("Sequencing run cannot start in the future", message_strs)
        self.assertIn("Sequencing run cannot end in the future", message_strs)


    def test_193_can_link_multiple_libraries_to_run_ok(self):

        library_name_1 = "HOOT-LIBRARY-ONE"
        library_o = models.LibraryArtifact(dice_name=library_name_1)
        library_o.save()

        library_name_2 = "HOOT-LIBRARY-TWO"
        library_o = models.LibraryArtifact(dice_name=library_name_2)
        library_o.save()

        run_name = "YYMMDD_AB000000_1234_ABCDEFGHI0"
        payload = {
            "runs": [
                {
                    "bioinfo_pipe_name": "ARTIC Pipeline (iVar)",
                    "bioinfo_pipe_version": "1.3.0",
                    "end_time": "2022-02-26 12:00",
                    "flowcell_id": "ABCDEF",
                    "flowcell_type": "v3",
                    "instrument_make": "ILLUMINA",
                    "instrument_model": "MiSeq",
                    "run_name": run_name,
                    "start_time": "2022-02-26 05:00"
                }
            ],
            "token": "oauth",
            "username": "oauth"
        }

        # Create sequencing process and link first lib
        payload["library_name"] = library_name_1
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)

        self.assertEqual(200, response.status_code)
        j = response.json()
        self.assertEqual(j["errors"], 0)

        # Assert run exists and process has a dnasequencingprocessrecord
        assert models.DNASequencingProcess.objects.filter(run_name=run_name).count() == 1
        process = models.DNASequencingProcess.objects.get(run_name=run_name)
        assert process.records.count() == 1

        # Check the sequencing process record
        assert models.DNASequencingProcessRecord.objects.filter(
                process=process,
                unique_name="%s-%s" % (run_name, library_name_1)
        ).count() == 1

        # Link second lib
        payload["library_name"] = library_name_2
        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)

        self.assertEqual(200, response.status_code)
        j = response.json()
        self.assertEqual(j["errors"], 0)

        # Assert process is linked with second dnasequencingprocessrecord
        process = models.DNASequencingProcess.objects.get(run_name=run_name)
        assert process.records.count() == 2

        # Check the sequencing process record
        assert models.DNASequencingProcessRecord.objects.filter(
                process=process,
                unique_name="%s-%s" % (run_name, library_name_2)
        ).count() == 1


    def test_add_basic_sequencing_name_too_short(self):
        process_count = models.DNASequencingProcess.objects.count()

        run_name = "lol"
        payload = {
            "library_name": self.library_name,
            "runs": [
                {
                    "bioinfo_pipe_name": "ARTIC Pipeline (iVar)",
                    "bioinfo_pipe_version": "1.3.0",
                    "end_time": "2022-01-25 15:00",
                    "flowcell_id": "ABCDEF",
                    "flowcell_type": "v3",
                    "instrument_make": "ILLUMINA",
                    "instrument_model": "MiSeq",
                    "run_name": run_name,
                    "start_time": "2022-01-25 05:00"
                }
            ],
            "token": "oauth",
            "username": "oauth"
        }

        response = self.c.post(self.endpoint, payload, secure=True, content_type="application/json", HTTP_AUTHORIZATION="Bearer %s" % self.token)
        self.assertEqual(200, response.status_code)

        j = response.json()
        self.assertEqual(j["errors"], 1)
        message_strs = []
        for message in j["messages"]:
            for k, v in message.items():
                message_strs.extend([x.get("message") for x in v])
        self.assertIn("Ensure this value has at least 5 characters", "".join(message_strs))
