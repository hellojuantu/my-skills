import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_idea_dependencies.py"
POM = """<?xml version="1.0"?>
<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>{group}</groupId>
  <artifactId>{artifact}</artifactId>
  <version>{version}</version>
</project>
"""


def write_properties(root):
    values = {
        "cloudcanal": "cg.utils.version=1\ncg.parser.version=1\ncg.schema.version=1\n"
        "cg.rdp.version=1\ncg.lib.driver.version=1\ncg.project.version=1\ncg.sdk.version=1\n",
        "clougence-utils": "cg.utils.version=1\n",
        "clougence-parser": "cg.parser.version=1\n",
        "clougence-schema": "cg.schema.version=1\n",
        "clougence-rdp": "cg.project.version=1\ncg.license.version=8\n",
        "clougence-drivers": "cg.drivers.api.version=1\n",
    }
    for name, text in values.items():
        path = root / name / "gradle.properties"
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")


def write_artifact(source, group, artifact, version):
    directory = source.joinpath(*group.split("."), artifact, version)
    directory.mkdir(parents=True)
    stem = f"{artifact}-{version}"
    (directory / f"{stem}.pom").write_text(
        POM.format(group=group, artifact=artifact, version=version),
        encoding="utf-8",
    )
    (directory / f"{stem}.jar").write_bytes(b"jar")


def write_series(source, license_artifact):
    write_artifact(source, "com.clougence", "clougence-utils", "1")
    write_artifact(source, "com.clougence", "cg-parser-base", "1")
    write_artifact(source, "com.clougence", "cg-schema-api", "1")
    write_artifact(source, "com.clougence", "cg-driver-api", "1")
    write_artifact(source, "com.clougence.rdp", "rdp-meta", "1")
    write_artifact(source, "com.clougence.cloudcanal", "base-api", "1")
    write_artifact(source, "com.clougence.cloudcanal", "cloudcanal-sdk", "1")
    write_artifact(source, "com.clougence.license", license_artifact, "8")


class SyncIdeaDependenciesTest(unittest.TestCase):
    def test_prefix_artifact_does_not_satisfy_the_exact_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            source = root / "source"
            target = root / "target"
            target.mkdir()
            write_properties(workspace)
            write_series(source, "license-sdk-extra")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--workspace",
                    str(workspace),
                    "--source",
                    str(source),
                    "--target",
                    str(target),
                ],
                capture_output=True,
                text=True,
            )
            copied = list(target.rglob("*"))
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("license-sdk", result.stderr)
        self.assertEqual([], [path for path in copied if path.is_file()])

    def test_exact_name_and_hyphen_prefix_are_copied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            source = root / "source"
            target = root / "target"
            target.mkdir()
            write_properties(workspace)
            write_series(source, "license-sdk")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--workspace",
                    str(workspace),
                    "--source",
                    str(source),
                    "--target",
                    str(target),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((target / "com/clougence/license/license-sdk/8/license-sdk-8.jar").is_file())
            self.assertTrue((target / "com/clougence/cg-parser-base/1/cg-parser-base-1.jar").is_file())
            self.assertIn("SHA-256 verified", result.stdout)
