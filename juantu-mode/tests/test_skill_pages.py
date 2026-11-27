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

    def test_continued_description_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "SKILL.md"
            skill.write_text(
                "---\n"
                "name: demo\n"
                "description: Develop and build CloudCanal\n"
                "  on Air or Pro.\n"
                "---\n\n"
                "# Demo\n",
                encoding="utf-8",
            )
            folded = Path(directory) / "folded.md"
            folded.write_text(
                "---\nname: demo\ndescription: >-\n  Develop and build CloudCanal.\n---\n\n# Demo\n",
                encoding="utf-8",
            )
            continued = run_check(skill)
            folded_result = run_check(folded)
        self.assertEqual(1, continued.returncode)
        self.assertIn("Description must stay on one line.", continued.stderr)
        self.assertEqual(1, folded_result.returncode)
        self.assertIn("Description must stay on one line.", folded_result.stderr)

    def test_example_and_hidden_headings_are_not_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "SKILL.md").write_text(
                "---\nname: demo\ndescription: One line is enough.\n---\n\n"
                "# Demo\n\n"
                "Use `[text](missing.md#nope)` as the example.\n",
                encoding="utf-8",
            )
            (root / "tilde.md").write_text(
                "# Guide\n\n~~~\n## Hidden target\n~~~\n\nSee [hidden](#hidden-target).\n",
                encoding="utf-8",
            )
            (root / "comment.md").write_text(
                "# Guide\n\n<!--\n## Hidden target\n-->\n\nSee [hidden](#hidden-target).\n",
                encoding="utf-8",
            )
            (root / "guide.md").write_text("# Guide\n\n## Real\n", encoding="utf-8")
            (root / "AGENTS.md").write_text(
                "See [missing][gone].\n\n[gone]: guide.md#not-a-heading\n",
                encoding="utf-8",
            )
            (root / "titled.md").write_text(
                "See [missing](guide.md#not-a-heading \"title\").\n",
                encoding="utf-8",
            )
            example = run_check(root / "SKILL.md")
            tilde = run_check(root / "tilde.md")
            comment = run_check(root / "comment.md")
            reference = run_check(root)
            titled = run_check(root / "titled.md")
        self.assertEqual(0, example.returncode, example.stderr)
        self.assertEqual(1, tilde.returncode)
        self.assertIn("#hidden-target", tilde.stderr)
        self.assertEqual(1, comment.returncode)
        self.assertIn("#hidden-target", comment.stderr)
        self.assertEqual(1, reference.returncode)
        self.assertIn("#not-a-heading", reference.stderr)
        self.assertEqual(1, titled.returncode)
        self.assertIn("#not-a-heading", titled.stderr)

    def test_rendered_heading_anchors_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "close.md").write_text("## Title ##\n\nSee [Title](#title).\n", encoding="utf-8")
            (root / "close-wrong.md").write_text("## Title ##\n\nSee [Title](#title-).\n", encoding="utf-8")
            (root / "amp.md").write_text("## Foo & Bar\n\nSee [right](#foo--bar).\n", encoding="utf-8")
            (root / "amp-wrong.md").write_text("## Foo & Bar\n\nSee [wrong](#foo-bar).\n", encoding="utf-8")
            (root / "dup.md").write_text("# Foo\n\n# Foo\n\n# Foo-1\n\nSee [third](#foo-1-1).\n", encoding="utf-8")
            (root / "setext.md").write_text("Hello\n-----\n\nSee [it](#hello).\n", encoding="utf-8")
            close = run_check(root / "close.md")
            close_wrong = run_check(root / "close-wrong.md")
            amp = run_check(root / "amp.md")
            amp_wrong = run_check(root / "amp-wrong.md")
            duplicate = run_check(root / "dup.md")
            setext = run_check(root / "setext.md")
        self.assertEqual(0, close.returncode, close.stderr)
        self.assertEqual(1, close_wrong.returncode)
        self.assertIn("#title-", close_wrong.stderr)
        self.assertEqual(0, amp.returncode, amp.stderr)
        self.assertEqual(1, amp_wrong.returncode)
        self.assertIn("#foo-bar", amp_wrong.stderr)
        self.assertEqual(0, duplicate.returncode, duplicate.stderr)
        self.assertEqual(0, setext.returncode, setext.stderr)
