import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path("cloudcanal-dev-test/skills/cc-setup/scripts/link-skills.sh")
REPO = Path(__file__).resolve().parents[2]


class LinkSkillsTest(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.checkout = self.root / "my skills"
        self.install = self.root / "installed"
        self.install.mkdir()
        self.dest = self.install / "pstack"
        self.legacy = self.checkout / ".codex/skills/pstack"
        for skill in ("pstack", "cloudcanal-dev-test", "datasource-lab", "cloudcanal-console-automation", "juantu-mode"):
            (self.checkout / skill).mkdir(parents=True)
        script = (REPO / SCRIPT).read_text()
        destination = 'skills_dir=${HOME}/.codex/skills'
        self.assertEqual(script.count(destination), 1)
        installer = self.checkout / SCRIPT
        installer.parent.mkdir(parents=True)
        installer.write_text(script.replace(destination, 'skills_dir=$TEST_INSTALL_DIR'))

    def run_installer(self):
        return subprocess.run(
            ["sh", str(self.checkout / SCRIPT)],
            env={**os.environ, "TEST_INSTALL_DIR": str(self.install)},
            capture_output=True,
            text=True,
        )

    def test_migrates_absolute_and_relative_dangling_legacy_links(self):
        for target in (self.legacy, os.path.relpath(self.legacy, self.install)):
            with self.subTest(target=target):
                self.dest.unlink(missing_ok=True)
                self.dest.symlink_to(target)
                result = self.run_installer()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.dest.resolve(strict=True), self.checkout / "pstack")

    def test_migrates_dangling_legacy_target_written_relative_to_checkout_parent(self):
        self.dest.symlink_to(Path(self.checkout.name) / ".codex/skills/pstack")
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.dest.resolve(strict=True), self.checkout / "pstack")

    def test_preserves_dangling_link_into_a_different_existing_checkout(self):
        other_checkout = self.install / self.checkout.name
        (other_checkout / "pstack").mkdir(parents=True)
        target = Path(self.checkout.name) / ".codex/skills/pstack"
        self.dest.symlink_to(target)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(os.readlink(self.dest), str(target))

    def test_preserves_unrelated_links(self):
        external = self.root / "another checkout"
        external.mkdir()
        intermediate = self.checkout / "forward"
        intermediate.symlink_to(external, target_is_directory=True)
        for target in (
            external / ".codex/skills/pstack",
            self.legacy.with_name("datasource-lab"),
            self.checkout / "other/pstack",
            intermediate / "pstack",
        ):
            with self.subTest(target=target):
                self.dest.unlink(missing_ok=True)
                self.dest.symlink_to(target)
                result = self.run_installer()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(str(self.dest), result.stderr)
                self.assertEqual(os.readlink(self.dest), str(target))

        (self.checkout / ".codex").symlink_to(external, target_is_directory=True)
        self.dest.unlink()
        self.dest.symlink_to(self.legacy)
        result = self.run_installer()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(os.readlink(self.dest), str(self.legacy))

    def test_preserves_current_relative_link_and_existing_directory(self):
        target = os.path.relpath(self.checkout / "pstack", self.install)
        self.dest.symlink_to(target)
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(self.dest), target)
        self.dest.unlink()
        self.dest.mkdir()
        result = self.run_installer()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(str(self.dest), result.stderr)
        self.assertFalse(self.dest.is_symlink())
        self.assertTrue(self.dest.is_dir())
