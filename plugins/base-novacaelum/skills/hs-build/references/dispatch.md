# Dispatch: one task, one brief, one implementer

Turns one workplan task into one piece of work: a brief on disk that is the implementer's only source of requirements, and a ledger line. When you delegate, the brief is what keeps your own context clean for rulings and the implementer's context holding exactly one task.

## Steps

1. **Read the criteria back.** Open the task's criteria file. A criterion that cannot pass as written (a `<placeholder>` in a path, `exists` on a file already present, a test target that does not exist and that no task produces) is repaired before anything is built. The criteria were frozen at the draft gate, so the repair is a double-back the state file will count: write the ruling in the ledger and say so. Never build around a broken criterion.
2. **Record the base.** `git rev-parse HEAD` in the project, into the brief.
3. **Write the brief** to `runs/<slug>/build/<id>/brief.md`:

   ```markdown
   ## Context
   - Run, stage `build`, task `<id>`: <title>
   - What it is for: <the summary, and the tests it serves>
   - Read first: <the PRD section, the files it produces or changes, the interfaces earlier tasks produced>
   - Locked, do not reopen: <decisions from the PRD this task rests on>
   - Base commit: <sha>

   ## Your task
   <numbered steps, ending in: show RED, then GREEN (see tdd.md)>

   Acceptance, verbatim from the criteria file:
   - <each criterion's statement and verification>

   ## Out of scope
   - Files other in-progress tasks own: <paths>
   - The criteria file, the workplan, the PRD (frozen)

   ## Report (your final message)
   A status line (DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT or BLOCKED), then ## RED, ## GREEN, the commands you ran, and any concerns.

   ## Escalate if
   - a criterion cannot be made true by any test-first change: NEEDS_CONTEXT
   - the work needs a file another task owns: stop and name it
   ```

   Exact values (paths, names, strings) live in the brief and nowhere else.
4. **Pick the implementer.** Doing it yourself is fine for a small task. Delegating: one implementer per file set, never two on overlapping files, and several same-shaped one-line tasks go in one brief. Pick the least capable model that fits the task's shape and name it. Four or more subagents at once is a cost the user sees first.
5. **Ledger it.** `Task <id>: started (brief <path>, base <sha>)`.
6. **Handle the return by status.** First write the returned report to `runs/<slug>/build/<id>/report.md`: a report that isn't on disk is lost. Then:
   - `DONE`: check `## RED` and `## GREEN`, then close through the verifier.
   - `DONE_WITH_CONCERNS`: resolve correctness or scope concerns before closing; ledger the rest.
   - `NEEDS_CONTEXT`: add what's missing to the brief and go again.
   - `BLOCKED`: change something (context, model, a split, or a ruling on a plan defect) before trying again. Never the same dispatch twice.

## Self-review

- [ ] The brief was on disk before the work started.
- [ ] The criteria were read back, and any repair is a ruling in the ledger.
- [ ] No two implementers were ever on the same file.

Source: Nova Caelum (Apache-2.0). Derived from obra/superpowers `subagent-driven-development` (MIT).
