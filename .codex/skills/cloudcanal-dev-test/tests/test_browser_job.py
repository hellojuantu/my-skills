import base64
from datetime import datetime, timedelta, timezone
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


GATE = Path(__file__).resolve().parents[1] / "scripts" / "check_console_jobs.py"
CONSOLE = "http://mini:8111"
API = "/cloudcanal/console/api/v1/inner/datajob/"
CREATE = API + "create"
QUERY = API + "queryjob"
LIST = API + "listbypage"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlT344AAAAASUVORK5CYII=")

JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0"
    "Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACP/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8A"
    "P7//2Q=="
)


class BrowserJobTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.evidence = Path(temporary.name)
        self.query = self.evidence / "query.json"
        self.job = {"dataJobId": 1816, "dataTasks": [{"dataTaskId": 110, "dataTaskType": "FULL", "dataTaskStatus": "COMPLETE"}]}
        self.create = {"pageUrl": CONSOLE + "/#/data/job/create/process", "method": "POST",
                       "requestUrl": CONSOLE + CREATE, "httpStatus": 200, "code": "1", "dataJobId": 1816}

    def write(self, file, value):
        (self.evidence / file).write_text(json.dumps(value))

    def save_query(self, data, origin=CONSOLE):
        self.write("query.json", {"requestUrl": origin + QUERY, "data": data})

    def browser(self, detail_url=CONSOLE + "/#/data/job/1816"):
        self.write("create.json", self.create)
        self.write("detail.json", {"pageUrl": detail_url})
        (self.evidence / "detail.png").write_bytes(PNG)

    def run_gate(self, expected, message):
        result = subprocess.run([sys.executable, str(GATE), "browser-job", str(self.evidence), str(self.query)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stderr)
        self.assertIn(message, result.stdout + result.stderr)

    def test_historical_component_and_cli_reports(self):
        # Excerpts from the 2026-11-19 JDBC probe and the 2026-11-18 CLI creation of job 1816.
        (self.evidence / "mysql.log").write_text("PASS mysql writer=com.clougence.cloudcanal.mysql.worker.writer.MyTypedFieldWriter\n")
        self.run_gate(1, "create.json")
        (self.evidence / "shanghai.job-create").write_text("final precheck finished, items=0, failed=0\nData job created, id=1816\n")
        self.save_query(self.job)
        self.run_gate(1, "create.json")

    def test_same_job_from_creation_to_detail(self):
        self.browser()
        self.save_query(self.job)
        self.run_gate(0, "1816")
        self.browser(CONSOLE + "/#/data/job/1817")
        self.run_gate(1, "1816")
        self.browser()
        self.save_query({**self.job, "dataJobId": 1817})
        self.run_gate(1, "1816")

    def test_job_1889_structure_completed_before_start(self):
        self.create["dataJobId"] = 1889
        self.browser(CONSOLE + "/#/data/job/1889")
        structure = {"dataTaskId": 109, "dataTaskType": "BUILD_STRUCT", "dataTaskStatus": "COMPLETE"}
        full = {"dataTaskId": 110, "dataTaskType": "FULL", "dataTaskStatus": "INIT"}
        increment = {"dataTaskId": 111, "dataTaskType": "INCREMENT", "dataTaskStatus": "INIT"}
        job = {"dataJobId": 1889, "dataTasks": [structure, full, increment]}
        self.save_query(job)
        self.run_gate(1, "RUNNING or COMPLETE")
        full["dataTaskStatus"] = "RUNNING"
        self.save_query(job)
        self.run_gate(0, "1889")
        self.save_query({**job, "dataTasks": [structure]})
        self.run_gate(0, "1889")

    def test_origin_route_response_screenshot_and_start(self):
        self.save_query(self.job)
        for change in ({"pageUrl": CONSOLE + "/#/data/job/list"}, {"httpStatus": 500}, {"code": "0"},
                       {"method": "GET"}, {"requestUrl": "http://localhost:8111" + CREATE}):
            with self.subTest(change=change):
                self.browser()
                self.write("create.json", {**self.create, **change})
                self.run_gate(1, "create.json")
        self.browser()
        (self.evidence / "detail.png").write_bytes(b"")
        self.run_gate(1, "detail.png")
        self.browser(CONSOLE + "/data/job/1816?tab=status")
        self.save_query({**self.job, "dataTasks": [{"dataTaskId": 110, "dataTaskType": "FULL", "dataTaskStatus": "INIT"}]})
        self.run_gate(1, "RUNNING or COMPLETE")

    def test_query_cannot_cross_slots_or_discard_task_id(self):
        self.browser()
        self.save_query(self.job, "http://mini:8112")
        self.run_gate(1, "expected Console")
        self.save_query({**self.job, "dataTasks": [{"dataTaskType": "FULL", "dataTaskStatus": "COMPLETE"}]})
        self.run_gate(1, "dataTaskId")
        self.write("query.json", self.job)
        self.run_gate(1, "requestUrl")

    def test_actual_jpeg_or_png_screenshot(self):
        self.browser()
        self.save_query(self.job)
        (self.evidence / "detail.png").unlink()
        jpg = self.evidence / "detail.jpg"
        jpg.write_bytes(JPEG)
        self.run_gate(0, "1816")
        jpg.write_bytes(JPEG[:-2])
        self.run_gate(1, "detail.jpg")
        jpg.write_bytes(bytes.fromhex("ffd8ff") + bytes(32) + bytes.fromhex("ffd9"))
        self.run_gate(1, "detail.jpg")
        jpg.write_bytes(PNG)
        self.run_gate(1, "detail.jpg")

    def test_idle_binds_every_snapshot_to_worker_slot_and_current_release(self):
        captured = datetime.now(timezone.utc) - timedelta(seconds=1)
        start = (captured - timedelta(seconds=2)).isoformat()
        snapshot = {"requestUrl": CONSOLE + LIST, "workerIp": "172.30.210.4",
                    "capturedAt": captured.isoformat(), "data": {"allJobCounts": 0, "jobVos": []}}
        job = {"requestUrl": CONSOLE + QUERY, "workerIp": "172.30.210.4", "capturedAt": captured.isoformat(),
               "data": {"dataJobId": 1816, "fsmActive": False, "dataTasks": [], "childJobs": []}}
        page_path = self.evidence / "page.json"

        def verify(page, supplemental, expected, message):
            self.write(page_path.name, page)
            self.write(self.query.name, supplemental)
            command = [sys.executable, str(GATE), "idle", "--origin", CONSOLE, "--worker", "172.30.210.4",
                       "--not-before", start, str(page_path), "--job", str(self.query)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)
            self.assertIn(message, result.stdout + result.stderr)

        verify(snapshot, job, 0, "snapshots idle")
        for field, value, message in (("requestUrl", "http://mini:8112" + LIST, "expected Console"),
                                      ("workerIp", "172.30.213.4", "Worker"),
                                      ("capturedAt", "2024-01-01T00:00:00Z", "during this release")):
            with self.subTest(field=field):
                verify({**snapshot, field: value}, job, 1, message)
                if field == "requestUrl":
                    value = "http://mini:8112" + QUERY
                verify(snapshot, {**job, field: value}, 1, message)
        verify(snapshot["data"], job, 1, "Worker")
        verify(snapshot, {**job, "data": {**job["data"], "fsmActive": True}}, 1, "fsmActive=true")


if __name__ == "__main__":
    unittest.main()
