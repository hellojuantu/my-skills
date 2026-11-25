import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_frontend_parity.py"


class FrontendParityTest(unittest.TestCase):
    def audit(self, frontend, *options):
        return subprocess.run(
            [sys.executable, SCRIPT, "--frontend-dir", frontend, "--format", "json", *options],
            capture_output=True, text=True,
        )

    def test_rejects_a_directory_without_frontend_api_files(self):
        with TemporaryDirectory() as directory:
            result = self.audit(directory, "--core")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("src/services/http/api", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_a_selected_api_file_must_exist(self):
        with TemporaryDirectory() as directory:
            frontend = Path(directory)
            api = frontend / "src/services/http/api"
            api.mkdir(parents=True)
            (api / "dataJob.js").write_text(
                'export const services = {query: "/cloudcanal/console/api/v1/inner/datajob/queryjob"};\n',
                encoding="utf-8",
            )
            good = self.audit(frontend, "--api-file", "dataJob.js")
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads(good.stdout)["summary"]["frontendApis"], 1)

            missing = self.audit(frontend, "--api-file", "missing.js")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("missing.js", missing.stderr)
            self.assertEqual(missing.stdout, "")
