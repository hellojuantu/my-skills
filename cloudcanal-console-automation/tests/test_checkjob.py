import json
import unittest
from unittest.mock import call, patch

from test_auth import run_cli
from cc_console.client import ConsoleClient
from cc_console.datajob import QUERY_JOB_PATH, REPLAY_JOB_PATH


SESSION = ("--base-url", "https://console.example", "--cookie", "test-session")


def check_response(job_id, status, position):
    return {"code": "1", "data": {
        "dataJobId": job_id,
        "dataJobName": f"check-{job_id}",
        "currTaskStatus": status,
        "dataTasks": [{
            "dataTaskId": job_id + 100,
            "dataTaskType": "CHECK",
            "dataTaskStatus": status,
            "taskPosition": json.dumps(position),
        }],
    }}


class CheckJobCommandsTest(unittest.TestCase):
    def test_wait_for_scheduler_and_require_complete_zero_metrics(self):
        for command, position, expected in (
            ("wait-check-job", {"loss": 0, "diff": 0}, 0),
            ("check-job-wait", {"loss": 0, "diff": 1}, 2),
            ("wait-check-job", {"diff": 0}, 2),
        ):
            with self.subTest(command=command, position=position):
                responses = [check_response(7, "WAIT_START", {}), check_response(7, "COMPLETE", position)]
                with patch.object(ConsoleClient, "post_json", side_effect=responses) as post:
                    status, output, errors = run_cli(command, *SESSION, "--job-id", "7")
                self.assertEqual(expected, status, errors)
                self.assertEqual(post.call_args_list, [call(QUERY_JOB_PATH, {"jobId": 7})] * 2)
                result = json.loads(output)
                self.assertTrue(result["complete"])
                self.assertEqual(result["ok"], expected == 0)
                self.assertEqual(result["startActions"][0]["action"], "wait-start")
                task = result["children"][0]["tasks"][0]
                self.assertEqual((task["loss"], task["diff"]), (position.get("loss"), position["diff"]))

    def test_replay_each_requested_job_then_wait(self):
        def respond(path, payload):
            if path == REPLAY_JOB_PATH:
                return {"code": "1", "data": None}
            self.assertEqual(path, QUERY_JOB_PATH)
            return check_response(payload["jobId"], "COMPLETE", {"loss": 0, "diff": 0})

        for command in ("replay-check-job", "check-job-replay"):
            with self.subTest(command=command), patch.object(ConsoleClient, "post_json", side_effect=respond) as post:
                status, output, errors = run_cli(command, *SESSION, "--job-id", "7", "--job-id", "8", "--wait-before-seconds", "0")
                self.assertEqual(0, status, errors)
                result = json.loads(output)
                for index, job_id in enumerate((7, 8)):
                    replay = {"jobId": job_id, "dataJobName": f"check-{job_id}"}
                    self.assertEqual(call(REPLAY_JOB_PATH, replay), post.call_args_list[index * 2 + 1])
                    self.assertEqual(result["replayResults"][index], {"path": REPLAY_JOB_PATH, "payload": replay})
                self.assertEqual([7, 8], [job["jobId"] for job in result["children"]])
                self.assertTrue(result["ok"])
