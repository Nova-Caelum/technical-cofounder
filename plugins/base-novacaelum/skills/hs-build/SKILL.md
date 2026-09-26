---
name: hs-build
description: The fourth stage of the working loop. Use when a run's workplan has passed the draft gate and the software is still owed ("build it", "execute the plan", "run the tasks", "work through the plan"), or when a run sits at build with tasks not yet closed. Builds one task at a time test-first and closes each only on a verifier-lite verdict.
---

# hs-build: tasks to verdicts

The stage that turns planned tasks into closed tasks. It is deliberately thin and deliberately the only door: one implementer per task, test first, closure only by the verifier's verdict, exit only through the build gate.

Observed failure: every earlier attempt at this loop planned the build beautifully and never reached it. One planning skill had zero uses; one execution trail died two stages in.

## The rule

Build progress is a task closed by a verifier-lite verdict. Nothing else counts. Per task: brief, implement test-first, show RED then GREEN, run verifier-lite, read the verdict. Exit only through the build gate, which reads verdict files, never anyone's claim. Make rulings, not stalls: decide, write the ruling and its cost in `BUILD_LEDGER.md`, keep going. Stop only for the four stops below.

## When to use

Fires when:
- The last passed gate is `draft` and the next stage is `build`.
- The user says "build it", "execute the plan", "run the tasks".
- A run sits at `build` with tasks that have no passing verdict.

Does NOT fire for:
- Writing or changing the spec or the plan: `hs-draft`. Framing or tests: `hs-understand`.
- A run whose status is `live`. Build is over; that is `hs-live`.
- Reviewing what was built: `engineering-code-review`, or an independent `devops-lead`.

## The process

1. **Look around, then enter.** `git status` in the project: work that isn't yours, or a tree behind its remote, goes in the ledger before anything is edited. Then:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" set-node runs/<slug>/loop.state.json --node build
   ```
   Create or resume `runs/<slug>/BUILD_LEDGER.md`. Tasks with a passing verdict are done: never redo them. Read the workplan once; one todo per task.
2. **Conflict scan.** One ledger line per pair of tasks that share a file or an interface, and one per task whose criteria disagree with its `produces`. Rule on each before the first task starts: `Ruling: <what>, <why>, <cost if wrong>`.
3. **Per task: brief.** `references/dispatch.md`. Read the task's criteria back first; a criterion that cannot pass as written (a placeholder, `exists` on a present file) is a plan defect: rule on it, don't build around it. Write the brief to `runs/<slug>/build/<id>/brief.md`. If you hand the task to a subagent (usually `engineer`), one per file set, never two on overlapping files.
4. **Per task: implement.** `references/tdd.md`. RED observed for the right reason, GREEN observed on the same target, both pasted into `runs/<slug>/build/<id>/report.md`.
5. **Per task: close through verifier-lite.** From the project root:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/mcp/verifier.py" runs/<slug>/03_draft/criteria/<id>.json --root .
   ```
   (or the `verify` tool on the `cofounder` MCP server, with the same file). It writes `verdicts/<id>-<time>.json` and exits `0` pass, `1` fail, `2` uncertain.
   - `pass`: ledger `Task <id>: closed (verdict <file>)`.
   - `fail`: the evidence names what is false. Fix the work, never the criteria, and run it again.
   - `uncertain` on a `manual` criterion: that is a person's to attest. Collect it for step 7; it is not a deferral.
   - `uncertain` on anything else: the criterion cannot be checked as written. That is a plan defect; rule on it in the ledger.

   Never write or edit a verdict file by hand. The gate compares every verdict with the task's frozen criteria.
6. **Reconcile.** Write `runs/<slug>/RECONCILIATION.md`, one bullet per task, exactly:
   ```
   - <task id> → <done|deferred|live-test>  <free text: where the work landed>
   ```
   (`->` works too). Anything after the disposition is yours; headings and prose between bullets are ignored. A typo'd disposition reads as missing and the gate refuses, which is the intended direction. `live-test` is only for the task that is the person's live acceptance test. Then walk the PRD and the plan: everything that had to be built is built and wired. A task nobody closed because it looked done is exactly what this catches. No new tasks here.
7. **Put the manual items in front of the person.** If any `manual` criterion is open, write `runs/<slug>/REVIEW.md` from `references/review.md` and give its path in the conversation. When they confirm one, record their words in `runs/<slug>/build/<id>/attest.json`, `[{"statement": "<the exact criterion>", "attested_by": "<who>"}]`, and rerun the verifier with `--attest runs/<slug>/build/<id>/attest.json`. Only their words; never attest for them.
8. **Gate.**
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" gate-pass runs/<slug>/loop.state.json --node build --by <you> \
       --workplan runs/<slug>/03_draft/workplan.json --reconciliation runs/<slug>/RECONCILIATION.md \
       --verdicts verdicts --artifact runs/<slug>/BUILD_LEDGER.md
   ```
   - `0`: passed; `status` is now `live` and `current_node` stays `build`. Build is over. Enter `hs-live`; do not keep building here.
   - `1`: refused. A task is missing from the reconciliation, or declared done without a passing verdict on its own criteria from after the plan was filed. Fix the named task; never fix the reconciliation to match.
   - `3`: HOLD. Nothing is wrong except `manual` criteria waiting on a person. The message lists each one: that list is your agenda with them (step 7), not a wait.

   Then report every `Ruling:` line from the ledger, in order, with its cost, under "Rulings I made".

## The four stops

Come back to the user only for: an irreversible or destructive operation · a security-sensitive action · a side effect outside the project that norms say you ask about first (a merge to a shared branch, a publish, an outside message) · a plan so broken that every path forward is a guess. Everything else is a ruling.

## Red flags

| Thought | Reality |
|---|---|
| "The brief names a different process." | The brief can be stale; the stage is not. |
| "This tooling fix unblocks the task, so it's build work." | It is not a task in the plan. Ledger it, or take it back to draft. Observed failure: six hours and millions of tokens went into tracking machinery while zero planned tasks moved. |
| "I remember where we were." | Read the ledger, the state file and `git log`. Memory doesn't survive a compaction. |
| "The subagent said DONE and the tests pass." | DONE is a report. Closed is a verdict file with overall `pass`. |
| "It's six lines; I'll do it inline." | A mechanical consequence of the change you're making: do it and ledger it. A task's work: it goes through the task. |

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "The user said all of it, so parallelize everything." | Observed failure: "green light" was read as permission for sixteen subagents, and half a month's quota went in fifteen minutes. One implementer per file set; ask before a fourth. |
| "The work is done; the criteria are a formality." | Observed failure: seven criteria with a `<date>` placeholder in their paths, work finished, and not one could be closed. Read the criteria before building. |
| "Green status means it happened." | Observed failure: status checks reported success five times in one night while nothing changed. The verdict file is the status. |
| "The verdict is uncertain only because of a manual check, so it's basically done." | It is built work the person can check today. Leaving it unmentioned is failing to tell them it is ready. |

## Self-check

- Does each task's report show RED failing for the expected reason, then GREEN on the same target?
- Is each closed task backed by a verdict file I read, with overall `pass`?
- Is every ruling in the ledger with its cost, and reported under "Rulings I made"?
- Did the build gate exit 0, not just the last verifier run?

Source: Nova Caelum (Apache-2.0). Derived from obra/superpowers `subagent-driven-development` (MIT).
