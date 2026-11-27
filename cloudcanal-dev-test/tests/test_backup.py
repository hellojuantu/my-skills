import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest
import uuid


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup.py"


class BackupTest(unittest.TestCase):
    def setUp(self):
        self.task = "backup-fixture-" + uuid.uuid4().hex
        self.target = Path("/tmp/codex-backup") / self.task / "fixture-host"
        self.addCleanup(shutil.rmtree, self.target.parent, True)

    def invoke(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, timeout=10)

    def test_release_rollback_and_docker_pre_are_rejected_as_retained_backups(self):
        for path in (
            "datasource-lab/private/releases/sr-dev-20261127T052015Z/rollback",
            "/home/fixture/datasource-lab/private/releases/sr-dev-20261127T052015Z/rollback",
            "/cloudcanal/console/lib.pre-sr-dev-20261127T052015Z",
        ):
            with self.subTest(path=path):
                result = self.invoke("check-path", path)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("/tmp/codex-backup/<task>/<host-or-slot>", result.stderr)
                self.assertIn("backup.py directory or archive", result.stderr)

    def test_archive_has_private_permissions_and_restorable_bytes(self):
        with TemporaryDirectory() as source:
            config = Path(source) / "conf"
            config.mkdir()
            (config / "service.properties").write_bytes(b"private fixture\x00\xff")
            result = self.invoke("archive", "--task", self.task, "--scope", "fixture-host", "--source", config)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            archive = Path(receipt["archive"])
            manifest = Path(receipt["manifest"])
            self.assertEqual(archive.parent, self.target)
            for path in (self.target.parent, self.target):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
            for path in (archive, manifest):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(receipt["restore"][0]["restoreTarget"], str(config))
            with tarfile.open(archive, "r:gz") as bundle:
                member = receipt["restore"][0]["archiveMember"] + "/service.properties"
                self.assertEqual(bundle.extractfile(member).read(), b"private fixture\x00\xff")
            self.assertEqual(self.invoke("verify", manifest).returncode, 0)
            archive.write_bytes(archive.read_bytes() + b"corruption")
            failed = self.invoke("verify", manifest)
            self.assertEqual(failed.returncode, 1)
            self.assertIn("SHA-256", failed.stderr)

    def test_dump_can_be_written_directly_under_the_private_root(self):
        result = self.invoke("directory", "--task", self.task, "--scope", "fixture-host")
        self.assertEqual(result.returncode, 0, result.stderr)
        dump = Path(result.stdout.strip()) / "motherdata.sql"
        descriptor = os.open(dump, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write("CREATE TABLE fixture (id INT);\n")
        result = self.invoke("archive", "--task", self.task, "--scope", "fixture-host", "--source", dump,
                             "--restore-target", "MySQL database motherdata")
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["restore"][0]["restoreTarget"], "MySQL database motherdata")
        self.assertTrue(dump.exists(), "Archiving must not delete an input owned by its caller")

    def test_destination_cannot_escape_through_task_names_or_symlinks(self):
        for task in ("../outside", "task/another"):
            result = self.invoke("directory", "--task", task, "--scope", "fixture-host")
            self.assertEqual(result.returncode, 1)
        self.assertEqual(self.invoke("directory", "--task", self.task, "--scope", "fixture-host").returncode, 0)
        with TemporaryDirectory() as outside:
            link = self.target / "escape"
            link.symlink_to(outside, target_is_directory=True)
            result = self.invoke("check-path", link / "backup.tar.gz")
            self.assertEqual(result.returncode, 1)
            self.assertIn("symlink", result.stderr)


if __name__ == "__main__":
    unittest.main()
