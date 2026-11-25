import json
import os
from pathlib import Path
from shutil import copyfile
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-slot-connections.py"
SELECTION = ("--source-id", "8", "--source-id", "9")


class SlotConnectionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = TemporaryDirectory()
        cls.addClassCleanup(fixture.cleanup)
        root = Path(fixture.name)
        cls.script = root / "datasource-lab/scripts" / SCRIPT.name
        names = Path("cloudcanal-dev-test/scripts/mini_names.py")
        config = root / "cloudcanal-dev-test/skills/cc-setup/mini.env"
        for path in (cls.script, root / names, config):
            path.parent.mkdir(parents=True)
        copyfile(SCRIPT, cls.script)
        copyfile(SCRIPT.parents[2] / names, root / names)
        config.write_text("MINI_HOSTNAME=mini\nMINI_TAILSCALE_NAME=mini.example.test\n", encoding="utf-8")
        cls.env = os.environ.copy()
        for key in ("MINI_HOSTNAME", "MINI_TAILSCALE_NAME", "MINI_SSH_HOST"):
            cls.env.pop(f"CC_{key}", None)

    def setUp(self):
        self.inventory = {"dataSources": [{"id": i} for i in (7, 8, 9)]}
        self.expected = {"notBefore": "2020-01-01T00:00:00Z", "slots": {}}
        self.evidence = {"results": []}
        for slot in ("8111", "8112"):
            self.add_slot(slot)

    def add_slot(self, slot):
        sources = {"8": f"redis-{slot}", "9": f"ck-{slot}"}
        self.expected["slots"][slot] = {"cluster": "Default Cluster", "sources": sources}
        for instance_id in sources.values():
            self.evidence["results"].append({
                "pageUrl": f"http://mini:{slot}/#/ccdatasource",
                "instanceId": instance_id, "cluster": "Default Cluster",
                "status": "Successful", "testedAt": "2020-01-01T00:00:04Z",
            })

    def check(self, *options):
        with TemporaryDirectory() as directory:
            paths = []
            for name, data in (("inventory", self.inventory), ("expected", self.expected), ("evidence", self.evidence)):
                path = Path(directory, name + ".json")
                path.write_text(json.dumps(data), encoding="utf-8")
                paths.append(path)
            return subprocess.run([sys.executable, self.script, *paths, *options], env=self.env,
                                  text=True, capture_output=True)

    def test_subset_and_default_full_inventory(self):
        result = self.check(*SELECTION)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("4 data-source registrations", result.stdout)
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing MotherData IDs 7", result.stderr)
        self.inventory["dataSources"].pop(0)
        self.assertEqual(self.check().returncode, 0)

    def test_new_slot_requires_its_own_console_page(self):
        self.expected["slots"].clear()
        self.evidence["results"].clear()
        self.add_slot("8113")
        result = self.check("--slot", "8113", *SELECTION)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.evidence["results"][0]["pageUrl"] = "http://mini:8111/#/ccdatasource"
        result = self.check("--slot", "8113", *SELECTION)
        self.assertEqual(result.returncode, 1)
        self.assertIn("declared Mini Console data-source page", result.stderr)

        self.evidence["results"][0]["pageUrl"] = "http://mini.unrelated.test:8113/#/ccdatasource"
        result = self.check("--slot", "8113", *SELECTION)
        self.assertEqual(result.returncode, 1)
        self.assertIn("declared Mini Console data-source page", result.stderr)

    def test_manual_record_accepts_empty_motherdata_inventory(self):
        self.inventory["dataSources"].clear()
        self.expected["slots"] = {"8111": {
            "cluster": "Default Cluster", "sources": {"manual-postgres": "postgres-lab"},
        }}
        row = self.evidence["results"][0]
        row["instanceId"] = "postgres-lab"
        self.evidence["results"] = [row]

        result = self.check("--slot", "8111", "--source-id", "manual-postgres")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 data-source registrations", result.stdout)

        result = self.check("--slot", "8111", "--source-id", "8")
        self.assertEqual(result.returncode, 1)
        self.assertIn("absent from MotherData inventory: 8", result.stderr)

    def test_page_url_requires_the_configured_console_origin_and_route(self):
        row = self.evidence["results"][0]
        row["pageUrl"] = "https://mini.example.test:8111/#/ccdatasource"
        result = self.check(*SELECTION)
        self.assertEqual(result.returncode, 0, result.stderr)
        for url in (
            "ftp://mini:8111/#/ccdatasource",
            "//mini:8111/#/ccdatasource",
            "mini:8111/#/ccdatasource",
            "http://mini:8111/other#/ccdatasource",
            "http://mini:8111/?other=1#/ccdatasource",
            "http://user@mini:8111/#/ccdatasource",
            "http://@mini:8111/#/ccdatasource",
            "https://mini/#/ccdatasource",
            "https://mini:99999/#/ccdatasource",
            "http://[mini:8111/#/ccdatasource",
            "http://mini :8111/#/ccdatasource",
        ):
            with self.subTest(url=url):
                row["pageUrl"] = url
                result = self.check(*SELECTION)
                self.assertEqual(result.returncode, 1)
                self.assertIn("declared Mini Console data-source page", result.stderr)

    def test_install_or_registration_alone_fails(self):
        self.evidence["results"].clear()
        result = self.check(*SELECTION)
        self.assertEqual(result.returncode, 1)
        for slot in ("8111", "8112"):
            for source_id in (8, 9):
                self.assertIn(f"slot {slot}, MotherData ID {source_id}: missing Worker result", result.stderr)
        self.expected["slots"]["8111"]["sources"].clear()
        result = self.check(*SELECTION)
        self.assertEqual(result.returncode, 1)
        self.assertIn("slot 8111: missing MotherData IDs 8, 9", result.stderr)

    def test_selected_evidence_requires_current_page_results(self):
        row = self.evidence["results"][0]
        row["testedAt"] = "2019-12-31T23:59:59Z"
        result = self.check(*SELECTION)
        self.assertEqual(result.returncode, 1)
        self.assertIn("result predates this run", result.stderr)
        row.pop("pageUrl")
        result = self.check(*SELECTION)
        self.assertEqual(result.returncode, 1)
        self.assertIn("declared Mini Console data-source page", result.stderr)

    def test_invalid_selection_and_extra_mapping_fail(self):
        for source_id, message in (("8", "duplicate MotherData ID"), ("10", "absent from MotherData"),
                                   ("0", "positive MotherData ID"), ("08", "positive MotherData ID")):
            with self.subTest(source_id=source_id):
                result = self.check(*SELECTION, "--source-id", source_id)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
        self.expected["slots"]["8112"]["sources"]["7"] = "another"
        result = self.check(*SELECTION)
        self.assertEqual(result.returncode, 1)
        self.assertIn("outside the requested coverage", result.stderr)


if __name__ == "__main__":
    unittest.main()
