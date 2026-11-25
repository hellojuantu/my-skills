from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from slot_claim import change_claim, read_claim


class SlotClaimAccessTest(unittest.TestCase):
    def test_only_a_write_claim_can_enter_deploying(self):
        with TemporaryDirectory() as directory:
            private = Path(directory)
            registered = {"04": {"consolePort": 8114}}
            acquire = Namespace(command="acquire", slot="04", agent="Codex", machine="Pro", hostname="pro",
                                session_id=None, session_title=None, session_url=None, run_id="test",
                                branch="test", access="read")
            claim = change_claim(acquire, private, registered)["claim"]
            update = Namespace(command="update", slot="04", claim_id=claim["claimId"],
                               phase="deploying", access=None, job_id=None, note=None)
            owner_path = private / ".claim-04"

            with self.assertRaisesRegex(ValueError, "deployment requires a write claim"):
                change_claim(update, private, registered)
            self.assertEqual(read_claim(owner_path), claim)

            update.access = "write"
            deployed = change_claim(update, private, registered)["claim"]
            self.assertEqual((deployed["access"], deployed["phase"]), ("write", "deploying"))

            update.phase = None
            update.access = "read"
            with self.assertRaisesRegex(ValueError, "deployment requires a write claim"):
                change_claim(update, private, registered)
            self.assertEqual(read_claim(owner_path), deployed)


if __name__ == "__main__":
    unittest.main()
