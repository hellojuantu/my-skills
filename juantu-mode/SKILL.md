---
name: juantu-mode
description: "Use Juantu's working preferences when asked for /juantu-mode, juantu-mode, or to work in Juantu's style. Covers how to answer, when to confirm a plan, and how to write code a person can read. For Codex and Cursor."
disable-model-invocation: true
---

# Juantu mode

Codex and Cursor read this same file. Follow it when the user asks for `/juantu-mode`, or asks you to work in Juantu's way.

## State the scope before a wide change

Read before you edit. Write the scope down. When the change covers more than one repo, or it changes behavior already in use, give a plan and wait for the user to agree.

Write the plan in plain words. In a table, show the current behavior, the behavior after the change, and how you will verify it. Paste the key code in the chat, a few lines before the change and a few lines after.

When the user asks for [poteto-mode](../pstack/skills/poteto-mode/SKILL.md), follow that procedure. Open the skill that matches the work.

- To set a boundary, read [architect](../pstack/skills/architect/SKILL.md).
- To compare several plans, read [arena](../pstack/skills/arena/SKILL.md).
- To look at separate parts, read [swarm](../pstack/skills/swarm/SKILL.md).
- To find old callers, read [blast-radius](../pstack/skills/blast-radius/SKILL.md).

## Lead a bug answer with what the user sees

Answer the sentence the user just asked. When the user changes the question, answer the new one.

Open with the result the user can see. Put a command you ran in the answer, with its output. For a conclusion that comes from reading code, say that you read the code.

Then name the step that went wrong, put the value from that moment beside it, and paste the code in the chat. After you use [how](../pstack/skills/how/SKILL.md) or [why](../pstack/skills/why/SKILL.md), rewrite the answer in the sentences above. Do not submit the architecture explanation unchanged.

## Write code the next person can read in order

Let the next person follow the code in order. Make each decision at the earliest line that can make it. Return when the condition fails. If the condition holds, take the value, then call.

Write unrelated exits as separate `if` statements. Check for null, confirm the type, then read the field. Keep the condition short. Leave a blank line between adjacent early returns, and between a normal return and the condition above it. When one condition validates, calls, and chooses the return value, split it into an `if` and a normal return.

After one class of mistake has been corrected twice, change the implementation as [correct](../pstack/skills/correct/SKILL.md) says. Keep a rule that belongs to one project in that project.

The rules above are habits. Do not add a check script for one stretch of code. Delete a checker that only searches the skill text. A check has to fail on the wrong code or on the file you hand over.

## Change only this round, in repos you change

Find the closest pattern in the repo, and use it when it fits. Change only this round's problem.

Create or switch a task branch only in a repo you change. Leave a repo you do not change on its current branch. When you sync `dev`, or when you build dependencies, do not switch every repo to a branch of the same name.

## Report the result the user can see

Do not create a backup unless the user explicitly asks, and do not ask a second time whether to take a backup.

Run the tests the project requires. Then go through the user's usual entry once, and look at the result the user can see. When you have written data, read it back from the target.

Open the delivery with the result. Then name the tests you ran, the entry, and what you saw. When there is a task, include its ID. If you get stuck, write the step you stopped on, the prompt, and the steps you have not done.
