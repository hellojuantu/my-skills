# Collaborate between Codex and Claude

This method works in other codebases too. For CloudCanal, look up Mini deployment and datasource configuration from the skill entry. Send Claude only the technical background that the review or the fix needs.

## From reproduction to delivery

Do these in order.

1. Codex reproduces the problem first. Record the version, the real entry, the expected result, and the actual result. Find the smallest counterexample you can. Say whether the failure is storage, display, validation, or configuration. When a source or a target is involved, trace the full phase, the CDC phase, and CHECK separately. Also trace the typed path and the non-typed path that are actually enabled.
2. Hand the clear work to Claude. By default, give the user English they can forward. First write the symptom and the evidence you can repeat. Then name the code path Claude should check and the acceptance condition. Also name the existing behavior to keep, and the work to leave undone for now. When the user wants analysis first, say not to edit code until the affected entries are clear.
3. State who edits the code this round. When Claude edits, Codex reviews on its own and reads the session the user names. Codex also prepares the tests and the environment. Take over the code only when the user tells Codex to fix it. Give any one file to only one side. The patch and the test result then refer to the same edit.
4. Check Claude's reply item by item. Record a first inference, a source confirmation, a repository change, and a passing test as separate notes. Return to the call site and confirm that a component test covers the real entry. Follow shared readers, writers, serialization, and default configuration into the neighboring paths. Confirm that the regression case fails under the old behavior. Confirm that the case covers input that should match and input that should not match. Reading the conversation and reading the patch are both review. The user still decides whether to forward it.
5. Continue under the completion condition the user set. Only after every fix you will deliver is ready, sync and start the formal integration retest. Claude may pause, run out of quota, or leave the path unconfirmed. Tell the user what is already proved, and name the step that is stuck. Continue the verification you can do alone. After work resumes, read the patch state first. Do not repeat a verification you already ran.
6. Codex closes the work. Rerun the regression against the actual patch. When you need a real database, confirm the target read-back before you read the CHECK result. Compare the state before the fix with the state after the fix. Report the patch status and the test status. Include the case or job ID, the remaining difference, and the exact blocker. Change the code, commit, or push only when the user authorizes it.

## Use the user's Claude session

When the user has allowed direct collaboration and a terminal session is available, first confirm that the target is the Claude session the user named. Look at the current task, whether Claude is idle, and whether the input is empty. When Claude is busy, or a draft is already there, leave the session as you found it. Continue the work you can do alone.

The connection depends on the user's environment. An existing tmux session is one example. Write the handoff, the follow-up, and the feedback in English, in the user's words. Send only what the check, the edit, and the test need. Keep deployment details, hosts, credentials, other sessions, and the text of this skill on the local machine.

After you send, read back the latest message and the status. Confirm that it arrived and that the other side is continuing. When the status is unclear, read it back before you send again. A reply is only evidence for Codex to collect. The user still decides whether to accept an edit outside the scope, a commit, or a push.

## English handoff template

> Please verify the causal path for each reproduced issue, then make the smallest fix within the agreed scope. For each issue, here is the entry point, the observed result, and the expected result.
>
> [Insert the failing case, a passing control, and the relevant code paths.]
>
> Trace the actual feature entry points and confirm the behavior of any shared paths affected by your change. Add a regression test for the failing case and include the test output. Call out any behavior changes, existing failures, or coverage that still needs integration testing. Keep [out-of-scope item] out of this patch. Let me know which fixes are ready for independent review and retesting.

A complex change can take two handoffs. First ask Claude only to confirm the path and to compare approaches. After the user confirms the meaning, make the edit. Write the example from this round's evidence. Do not turn a temporary requirement from one business path into a general rule for other repositories.
