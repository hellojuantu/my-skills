# Rules for agents

| Rule | Check |
| --- | --- |
| Switch a task branch only in a repo you change. | There is no automatic check. At delivery, look at the current branch of each repo. |
| When you read a Console return value, use only the one field that value has in the API. Do not write an alias such as `fsmId` or `fsmID`. | `python3 cloudcanal-console-automation/scripts/check_console_field_aliases.py` |
| Do not check slot claims when you start a job. | `python3 cloudcanal-console-automation/scripts/check_no_invented_gates.py` |
| Read the Mini console host name from `mini.env`. Do not hard-code `http://mini:` in a script. | `python3 cloudcanal-console-automation/scripts/check_mini_host.py` |
| A claim query takes the shared lock. `change_claim` must take the exclusive lock. The comparison must see these calls, and must not check only the lock function. | `python3 cloudcanal-dev-test/skills/verify-slot-claim/scripts/code_matches_model.py` |
| A Mini release checks this round's `claimId` before it stops services. The release enters `deploying` on a `write` claim. Run an already authorized release directly. | `python3 cloudcanal-dev-test/scripts/test_slot_claim_access.py` checks that a `read` claim cannot enter the release phase. |
| After tests on Mini, keep the original write claim and set it to `awaiting-handoff`. When every slot is taken, list the sessions so the user can open them and decide. Release only the claim the user names, and only after the user explicitly asks. | `slot_claim.py release` requires `--user-confirmed` and checks the current `claimId`. On Mini, run `python3 cloudcanal-dev-test/tests/test_slot_claim.py` to verify handoff, every slot taken, and an old ID. |
| After you read the target back, stop the Mini incremental acceptance job this round created and started. When the user asks to keep it running, record the state. | `check_console_jobs.py stopped-test-job` checks the same job's receipt after the stop. |
| For an SSH identity check, click the signed-in Google account in Chrome. Hand the page to the user only when it asks for a password, MFA, or a verification code. | `python3 -m unittest cloudcanal-dev-test.tests.test_ssh_auth` |
| Do not create a backup unless the user explicitly asks. | `python3 -m unittest cloudcanal-dev-test.tests.test_backup` checks only paths and permissions. |
| Tests use the Console API by default. Open a browser only when the user asks to see the page. | `check_console_jobs.py api-job` accepts evidence with no screenshot. |
| A skill rewrite keeps each description on one line, and every markdown link lands on a heading or a file that is there. | `python3 -m unittest juantu-mode.tests.test_skill_pages` |
| Do not add a check that only searches skill text for required sentences. | There is no automatic check. `check_bug_explain.py` and `check_qa_template.py` were deleted because each one failed a correct edit. |
