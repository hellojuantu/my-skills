# Connect pstack to Codex and Claude

pstack v0.15.43 was written by Lauren Tan. The sibling `pstack/` directory keeps the original text, the scripts, and the [MIT license](../../pstack/LICENSE), with each file left as it is.

Pick a sub-skill from the [index](pstack-index.md) first. The flow follows [poteto-mode](../../pstack/skills/poteto-mode/SKILL.md). This page covers only how this install connects.

## Workspace rules

`cc-all-in-one`'s `AGENTS.md` points at the skills installed on this machine. It covers the agent roles, reverse-merging `dev`, the manual QA note, formatting before a commit, real Console acceptance, and the login handoff. How to carry them out is later on this page and in the [Mini flow](../SKILL.md).

Parallel agents use the `pstack-*.toml` files in `~/.codex/agents/`. When those files are missing, configure them as [Codex agents](../skills/cc-setup/SKILL.md#codex-agents) describes. After you change machines, confirm that the skill paths in `~/.codex/config.toml` still point at this install.

When an original flow asks you to understand an entry, find a root cause, or judge the impact, start from evidence. Collect a reproduction, a normal control, and the related code. For a protocol, a type conversion, or a cross-layer change, find the closest implementation in the repository. Check its input, its output, and its responsibility. When the call shape can stay, keep the existing entry and put the behavior difference in the layer that owns that meaning. CloudCanal tests run through the Mini test entry.

When the user names who does the work or who reviews it, follow that split. Hand work to Claude with the [English handoff](claude-collaboration.md).

When you verify through a real entry, first write down the result you will look at. For CloudCanal, keep the unit tests and the component tests. Also follow the [Mini flow](../SKILL.md) for API acceptance and a native read-back on the target. Operate the page only when the user explicitly asks for the page. Other repositories use their own tools.

When you rerun a flow that is already mature, reuse its original checks and its delivery requirements. Take the environment rules and the datasource rules from the current repository.

When you verify a protocol such as Binlog, compare `dev` and the current version on the same real protocol sample. Record the earliest step that fails. When you use a fixture, write the column definitions and the actual protocol encoding as separate notes. When the fixture and the real data disagree, the conclusion covers only the steps the fixture actually reached.

When the shared terminal is busy, you can still read code, prepare data, and run tests in a separate session. Write the results as separate parts: a source check, a unit test, a build, and a real-database read-back. When you pick an original flow, load only the sub-skill this step needs.

## Task branch scope

Create or switch a task branch only in a repository that has changes. For a fix in one repository, do not create a branch of the same name in the other repositories.

Syncing `dev`, building a dependency, and switching the task branch are three separate actions. Leave an unchanged repository on its current branch. When you need another version as a dependency, pin that SHA with a separate checkout or a worktree.

## Reverse-merge dev

A reverse merge covers every separate Git project under `cc-all-in-one`. In each repository, fetch `origin/dev` and look at the current branch and the working tree. Merge `origin/dev` into the feature branch. Fast-forward the local `dev` so it matches `origin/dev`.

After that, run:

```sh
python3 ~/.codex/skills/cloudcanal-dev-test/scripts/check_dev_merges.py
```

The script finds the projects on its own. It queries each remote `dev` directly and checks that those commits are in the current `HEAD`. On failure, it reports the missing commits, the conflict, or the other blocker for each repository.

## Name a local before you pass it

When an argument to a method or a constructor needs parsing, conversion, or a combination, hold it in a local first. Give that local a name that says what it means. A new or edited Java local uses its real type. Write `ZoneId sourceTimestampZone = ObDsUtil.toLogProxyZoneId(config.getSrcTimeZone());` first, then pass `sourceTimestampZone`. When you review Java added in this round, look for a local that still uses `var`.

## Update the manual QA document

When you create a QA note, copy the [CloudCanal internal QA template](qa-template.md). Fill the version, the branch, and the developer into the title. Under Developer self-test, add a `###` heading for each part of this round's scope. After you settle those headings, keep a baseline copy to compare against.

When the user gives you a draft or a template, keep a backup copy first. Edit the file they gave you. Keep its headings, its sections, its order, and its list format. Add cases and acceptance conditions inside the sections that are already there. Compare lists, tables, and links with the original.

Fill Background in the template order: developer, environment, agreed release time, and who the feature is for. Under Environment, write the real branch of each repository. Follow the template for repository order and for items that share one line. Check the original for the order and the list depth of developer, environment, agreed release time, and who the feature is for.

Put the Console entry and the job data in the matching Developer self-test case. In Requirement and in Fix, start a new capability line with the word Support. One such line is "Support a JDBC connection time zone on a TiDB source and a TiDB target."

Write the conclusion first under Developer self-test. For the feature in this QA note, write the result, the job config, the job ID, and the items still to test. Write a parameter name and its value as ordinary text, for example useTypedField=true. Match each item to this round's Requirement or Fix. Do not put a parameter name or a parameter value in inline backticks.

Leave a reverted change in the development record. Leave build, deploy, and rollback notes in that same record. Deliver Markdown that Yuque can import directly.

## Format the Java files before you commit

Before the commit, list every Java file this change touches. Include added files, edited files, and files whose names changed. Format each whole file with IntelliJ IDEA **Reformat Code**. In `cc-all-in-one`, use the project's `canal-format`. When that same file also has another task's edits, separate the part you will commit. After formatting, look at the diff and the staged range. Then commit. When you group files in IDEA by database or by the purpose of the change, use `pika-idea-control` to confirm which files sit in which changelist.

Check the whole of every Java file in this commit. Capitalize the first letter of English log text, including a log that is already there and the text after a tag. After you stage, run this from the repository root:

```sh
python3 ~/.codex/skills/cloudcanal-dev-test/scripts/check_java_log_initials.py
```

Fix the file and the line the report names. Stage that fix, then run the check again.

In a Java call that you split with `//`, end every argument with `//`, including the last argument. Put `);` on the next line by itself. The script checks only calls of this shape that are new in the current diff. Run this from the repository root:

```sh
python3 ~/.codex/skills/cloudcanal-dev-test/scripts/check_java_call_wrap.py
```

In a Java method or constructor that you add, or whose signature you change, every custom parameter needs a real use. After you stage, run this from the repository root on JDK 17 or newer:

```sh
java ~/.codex/skills/cloudcanal-dev-test/scripts/CheckJavaParameters.java
```

Follow each call to the business operation that finally reads the value. When the whole chain has no consumer, delete that parameter from the declaration and from the callers together.

The log-capitalization check and the Java parameter check read the staging area by default. To review a commit that already exists, add `--commit <commit>`. For Java edited in this round, pass file paths to the log check. It then checks each whole file in the working tree.

The `//` call check reads the diff from `HEAD` to the working tree, and it reads untracked Java files. The parameter check accepts `--between <old-commit> <new-commit>`. To narrow the check, put repository-relative paths after `--`.

The parameter check uses the JDK syntax tree to compare named-type member declarations in the two versions. It reports a parameter that never appears as an identifier in the method body. A comment, a string, and `this.ddl` do not count as a use of the parameter `ddl`. A plain pass-through, an assignment, or a same-named reference in a nested scope can still satisfy the check. Trace those cases by hand.

The check skips a declaration that has no method body. It also skips a method of a local class, a method of an anonymous class, a record constructor, and the standard `main(String[])`. To keep an inheritance contract, the check also skips `@Override` and a one-argument `equals`. It also skips an instance method that names a parent type and might override a parent method.

## Map original tools to Codex

When the original names a Cursor `Task` or a model, dispatch it as [Codex agents](../skills/cc-setup/SKILL.md#codex-agents) says. Dispatch in parallel the work you can accept on its own, such as a code review, data preparation, and log analysis. After a seat is free, dispatch the task you already prepared.

When you need an independent review and no separate reviewer is available, write in the acceptance record which checks actually ran. When the original waits on the current task with `/loop`, keep checking in this Codex session. Stop when a completion condition appears, or when you hit a concrete blocker.

The original may mention an external session, a plugin install, or an automation. It may also mention a push, opening a PR, or a merge. Follow the permission the user gave for this task.
