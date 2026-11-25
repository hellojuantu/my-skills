import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
from threading import Thread
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-deployment-route.py"
TEMPLATES = [
    {"id": 5, "family": "MONGODB", "dockerImage": "mongo:8.0"},
    {"id": 25, "family": "REDIS", "dockerImage": "redis:8.2.10-bookworm"},
]


class CatalogHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/ds-types":
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(self.server.payload).encode())

    def log_message(self, *args):
        pass


class DeploymentRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), CatalogHandler)
        Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)

    def run_check(self, *args):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        return subprocess.run([sys.executable, str(SCRIPT), origin, *args], text=True, capture_output=True)

    def test_manual_deployment_precondition(self):
        self.server.payload = {"code": "OK", "data": TEMPLATES}
        for args, status, ids in [
            (["Mongo"], 1, [5]),
            (["Redis"], 1, [25]),
            (["OB"], 0, []),
            (["MongoDB", "--exact-image", "docker.io/library/mongo:8.0"], 1, [5]),
            (["MongoDB", "--exact-image", "mongo:7.0"], 0, []),
            (["MongoDB", "--exact-image", "example.test:5443/library/mongo:8.0"], 0, []),
        ]:
            with self.subTest(args=args):
                result = self.run_check(*args)
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(json.loads(result.stdout)["matchingTemplateIds"], ids)

    def test_uncertain_route(self):
        for rows, args in [
            ([], ["OB"]),
            (TEMPLATES + [{"id": 26}], ["OB"]),
            (TEMPLATES, ["Monggo"]),
            (TEMPLATES, ["MongoDB", "--exact-image", "redis:8.2.10-bookworm"]),
        ]:
            with self.subTest(rows=rows, args=args):
                self.server.payload = {"code": "OK", "data": rows}
                result = self.run_check(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
