import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
from threading import Thread
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-service.py"


class MotherDataHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/actuator/health":
            payload = {"status": "UP"}
        elif self.path in self.server.rows:
            payload = {"code": "OK", "data": self.server.rows[self.path]}
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, *args):
        pass


class ServiceInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), MotherDataHandler)
        Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)

    def setUp(self):
        self.server.rows = {
            "/api/nodes": [{"id": 1}],
            "/api/database-install-runs": [{"id": 1, "status": "PENDING"}],
            "/api/data-sources": [{"id": 1}],
        }

    def check(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        return subprocess.run([sys.executable, SCRIPT, origin], capture_output=True, text=True)

    def test_installations_keep_unassigned_data_source(self):
        rows = self.server.rows["/api/database-install-runs"]
        rows.extend([{"id": 3, "status": "SUCCESS", "dataSourceId": 1},
                     {"id": 2, "status": "PENDING", "dataSourceId": None}])
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["installations"], [
            {"id": 1, "status": "PENDING", "dataSourceId": None},
            rows[2], rows[1],
        ])

    def test_duplicate_ids_in_each_record_type(self):
        for path, rows in self.server.rows.items():
            with self.subTest(path=path):
                rows.append(rows[0])
                result = self.check()
                rows.pop()
                self.assertEqual(result.returncode, 1)
                self.assertIn("Duplicate record ID", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_installations_require_a_status(self):
        for fields in ({}, {"status": None}, {"status": "  "}, {"status": 3}):
            with self.subTest(fields=fields):
                self.server.rows["/api/database-install-runs"] = [{"id": 1, **fields}]
                result = self.check()
                self.assertEqual(result.returncode, 1)
                self.assertIn("Missing or invalid status for installation 1", result.stderr)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
