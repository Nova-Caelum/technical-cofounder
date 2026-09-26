---
name: hs-draft
description: The third stage of the working loop. Use when a run's decision has passed the decide gate and nothing is planned yet ("write the PRD", "write the plan", "spec it and plan it", "break this into tasks"). Renders the frozen decision into a spec (PRD.md) and a plan (workplan.json), where every task carries a criteria file a verifier can close.
---

# hs-draft: the spec and the plan

Render the frozen decision into a specification and a plan, and exit only when every task in the plan is tracked work: an id, the tests it serves, and a criteria file verifier-lite can run. A plan that never becomes tracked work is indistinguishable from a plan nobody wrote.

Observed failure: a planning skill sat loaded for weeks with zero uses and its output folder was never created. Plans were written in chat and never became anything a gate could read.

## The rule

Enter the stage. Read the frozen `02_decide/` and `01_understand/` files. Write `03_draft/PRD.md` (`references/prd.md`), then `03_draft/workplan.json` and one `03_draft/criteria/<task-id>.json` per task (`references/plan.md`). Leave only through the draft gate, which freezes the workplan and every criteria file it names. Each reference carries its own self-review; run it and fix inline. No reviewer subagent.

## When to use

Fires when:
- The last passed gate is `decide` and the next stage is `draft`.
- The user says "write the PRD", "write the plan", "spec it and plan it", "break this into tasks" about a goal whose decision is frozen.
- A run sits at `draft` and its workplan has not passed the gate.

Does NOT fire for:
- A goal with no frozen `mapping.json`: `hs-decide` first.
- Building the tasks: `hs-build`.
- Editing a frozen PRD or workplan after the gate. That is a double-back, counted by the state file.

## The process

1. **Enter.**
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" set-node runs/<slug>/loop.state.json --node draft
   ```
   Number the tests `T1..TN` exactly as decide did. The mapping's kept components are the v1 set.
2. **Spec.** `references/prd.md`. `PRD.md` with its fixed sections: the acceptance set verbatim, one page of what is being built, the components rendered from `mapping.json` (never a new one), the principles cited, a plain v2 recap, the decisions inherited, what v1 does not claim, and the rules only prose enforces.
3. **Plan.** `references/plan.md`. `workplan.json`: every task with an id, a plain summary, the tests it serves, the files it produces, what blocks it, and a criteria file. Every test `T1..TN` is served by at least one task.
4. **Gate.**
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" gate-pass runs/<slug>/loop.state.json --node draft --by <you> \
       --workplan runs/<slug>/03_draft/workplan.json --artifact runs/<slug>/03_draft/PRD.md
   ```
   Exit 0 freezes the workplan, every criteria file it names, and the PRD. The gate's pass time is also the filing time: at build, a verdict older than it does not count.

## What the gate checks

The workplan parses and has tasks; its `tests_file` resolves; every task id is unique and made of `[A-Za-z0-9_.-]`; every `serves` id is a real test; every test is served by some task; every task's criteria file exists, is a valid verifier-lite criteria file, carries the task's id as its `id`, and has at least one criterion that is not `manual` (an all-manual task can never be closed by a verifier). It cannot see whether a criterion can fail today, or whether a task's criteria really test what it serves. That is the self-review in `plan.md`.

## The stops

Come back to the user only for: a test no task can serve (a design gap, so a double-back to decide) · a task whose honest size is more than one working session (say so in its `size`; splitting, deferring or dropping it is their call) · when the user is present, one question at the end of step 2: accept the v1 set as rendered, or override. Everything else is a call you make and record under `## Decisions inherited`.

## Red flags

| Thought | Reality |
|---|---|
| "The task is obvious from the plan's flow; the fields are padding." | A fresh implementer reads one task and nothing else. Observed failure: a plan that dropped context for density was judged "not even vaguely stand-alone". |
| "The implementer will name the file." | `produces` names every file by its decided path. A task whose output is "the thing it makes" can't be planned by someone who wasn't in the conversation. |
| "The PRD is where the architecture gets written properly." | Components come from `mapping.json`. A new component is a double-back to decide. |
| "The deferred list is in Deferred.md; the PRD needn't repeat it." | That context is exactly what gets lost. `## v2 recap`, plain, no reasoning. |
| "It validated, so the criterion is fine." | Observed failure: seven criteria with a `<date>` placeholder validated and could never pass. A criterion can be false today and names the change that makes it true. |

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "The plan is written; we'll make the tasks real when we build." | The gate is what makes them real. Build has no door without a filed workplan. |
| "I'll split the manual check into its own task." | A task whose criteria are all manual can never be closed by a verifier, and the gate refuses it. The attestation rides on the task whose work it judges. |
| "One task per criterion keeps things tidy." | A task is the smallest unit that carries its own criteria and is worth a verdict. Fold setup and docs into the task that needs them. |

## Self-check

- Did the gate exit 0? Its reading, not mine.
- Is every acceptance test served by a task, and does `## Components` name nothing the mapping lacks?
- Do `## Principles`, `## v2 recap` and `## Closeout` carry content, not just headings?

Source: Nova Caelum (Apache-2.0). Derived from obra/superpowers `writing-plans` (MIT).
