import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECK = Path(__file__).resolve().parents[1] / "scripts" / "check_skill_pages.py"


def run_check(*paths):
    return subprocess.run(
        [sys.executable, str(CHECK), *[str(path) for path in paths]],
        capture_output=True,
        text=True,
    )


class SkillPageCheck(unittest.TestCase):
    def test_current_pages_resolve(self):
        result = run_check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Skill pages resolve:", result.stdout)

    def test_old_heading_anchor_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide = root / "guide.md"
            guide.write_text("# Guide\n\n## Codex agents\n", encoding="utf-8")
            notes = root / "AGENTS.md"
            notes.write_text(
                "See [Codex agents](guide.md#codex-代理).\n",
                encoding="utf-8",
            )
            result = run_check(root)
        self.assertEqual(1, result.returncode)
        self.assertIn("AGENTS.md", result.stderr)
        self.assertIn("#codex-代理", result.stderr)
        self.assertIn("guide.md", result.stderr)

    def test_split_description_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "SKILL.md"
            skill.write_text(
                "---\nname: demo\ndescription:\n  Develop and build CloudCanal.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            result = run_check(skill)
        self.assertEqual(1, result.returncode)
        self.assertIn("SKILL.md", result.stderr)
        self.assertIn("Description must stay on one line.", result.stderr)
