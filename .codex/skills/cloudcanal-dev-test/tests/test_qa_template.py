from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check_qa_template.py"
TEMPLATE = "# 提测稿\n\n## 需求\n\n## 修复\n\n## 开发自测\n"
REJECTED_TIDB_ITEM = "- TiDB 源端和目标端的 JDBC 连接支持 `connectTimeZone`。默认用 `Asia/Shanghai`。"
CORRECTED_TIDB_ITEM = "- 支持 TiDB 源端和目标端配置 JDBC 连接时区 `connectTimeZone`，默认值为 `Asia/Shanghai`。"


class QaTemplateTest(unittest.TestCase):
    def check(self, candidate, original=None):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            template_path = path / "template.md"
            candidate_path = path / "candidate.md"
            template_path.write_text(TEMPLATE, encoding="utf-8")
            candidate_path.write_text(candidate, encoding="utf-8")
            command = [sys.executable, str(CHECKER), str(template_path), str(candidate_path)]
            if original is not None:
                original_path = path / "original.md"
                original_path.write_text(original, encoding="utf-8")
                command.extend(["--original", str(original_path)])
            return subprocess.run(command, capture_output=True, text=True)

    def test_rejects_actual_ti_db_wording(self):
        candidate = TEMPLATE.replace("## 修复\n", f"## 修复\n\n{REJECTED_TIDB_ITEM}\n")
        result = self.check(candidate)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("candidate.md:7: 新增支持条目请以「支持」开头", result.stderr)

    def test_accepts_corrected_ti_db_wording(self):
        candidate = TEMPLATE.replace("## 修复\n", f"## 修复\n\n{CORRECTED_TIDB_ITEM}\n")
        result = self.check(candidate)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_checks_only_new_or_rewritten_summary_items(self):
        original = TEMPLATE.replace("## 需求\n", f"## 需求\n\n{REJECTED_TIDB_ITEM}\n")
        result = self.check(original, original=original)
        self.assertEqual(result.returncode, 0, result.stderr)
        rewritten = original.replace("默认用", "默认值为")
        result = self.check(rewritten, original=original)
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_preserves_other_bullets_and_fenced_examples(self):
        candidate = TEMPLATE.replace(
            "## 修复\n",
            "## 修复\n\n- 修复 TiDB 不支持 `connectTimeZone` 的问题。\n"
            "- 开放 SQL Server -> Paimon 全量迁移。\n"
            "- 旧版 TiDB 不支持 `connectTimeZone`。\n"
            f"\n```markdown\n{REJECTED_TIDB_ITEM}\n```\n",
        ) + f"\n{REJECTED_TIDB_ITEM}\n"
        result = self.check(candidate)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_still_rejects_heading_changes(self):
        result = self.check(TEMPLATE.replace("## 开发自测", "## 测试"))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("section headings", result.stderr)
