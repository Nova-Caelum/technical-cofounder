---
name: hs-understand
description: The first stage of the working loop. Use when a goal arrives unframed ("let's figure out what we're building", "spec this out", "what does done look like", "is this worth doing") or when a run has no tests.json yet. Finds the real problem, holds the stated constraints hard, and writes the acceptance tests before anything is designed.
---

# hs-understand: frame the goal, write the tests

Find the real problem, hold the stated constraints hard, and write the tests that define finished, before anything is designed. The design shrinks by construction only when the test already exists: cutting needs something to cut against. And one test must walk the whole path, because every component can pass its own unit test while the thing is unwired.

Observed failure: a system's acceptance gates were written near the end of a long spec, so the architecture was designed without the test in view and a stage was marked done against a mock.

## The rule

Triage first and say the path out loud: spike, bounded or architectural. A spike opens no run and writes nothing; it ends in the conversation with an answer. Bounded and architectural open a run, write `01_understand/Problem.md` and `01_understand/tests.json`, and leave only through the understand gate. Ceremony scales with the path; the gate never does.

## When to use

Fires when:
- A goal arrives that nobody has framed: a feature, a subsystem, a tool, a "should we".
- There is no `loop.state.json` for the goal, or it reads `current_node: framing`.
- A run sits at `understand` and its `tests.json` has not passed the gate.

Does NOT fire for:
- Options, architecture, cuts: `hs-decide`. The spec and the plan: `hs-draft`. Building: `hs-build`.
- A failure whose problem is already known. That is debugging.
- A spike's follow-up ("the probe worked, keep it"). That is a new request; triage it again.

## The process

1. **Triage.** Read `references/triage.md`. Say the classification before your first question. Spike: go to 2s. Otherwise go to 2. When in doubt, take the heavier path.
2. **Open the run.** From the project root, write the ask verbatim to `runs/<slug>/original_input.md`, then:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" init --goal <slug> --input runs/<slug>/original_input.md --workspace runs
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" set-node runs/<slug>/loop.state.json --node understand
   ```
   The state file is the goal's registration: a run that stops here still exists.
   - **2s. Spike.** No run, no files, no gate. Say the question and what you will try in two or three sentences, find out as cheaply as correctness allows, and report a recommendation. Anything you built is labelled throwaway.
3. **Problem.** Follow `references/problem.md`. It writes `Problem.md`: the ask verbatim, the path, the real problem and for whom, every stated constraint marked HARD, an assumptions register, and what is out of scope.
4. **Tests.** Follow `references/tests.md`. It writes `tests.json` in the verifier-lite criteria format: every criterion typed and checkable, at least one not `manual`, at least one statement beginning `WHOLE-PATH:`. Paths are relative to the project root, because that is where the verifier runs.
5. **Gate.**
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" gate-pass runs/<slug>/loop.state.json --node understand --by <you> \
       --tests runs/<slug>/01_understand/tests.json --artifact runs/<slug>/01_understand/Problem.md
   ```
   Exit 0 freezes both files. Exit 1 names every problem at once: fix them and run it again. Entering `decide` is `hs-decide`'s first line, not yours.

## What the gate checks

`tests.json` parses; every criterion has a statement and a known kind (`file_state`, `command_check`, `manual`); paths are relative, stay inside the project and carry no `<placeholder>`; `contains` has an expected string and `modified_after` a timestamp; at least one criterion is not `manual`; at least one statement begins `WHOLE-PATH:`. It cannot see whether a criterion could fail today. That is the self-check below, and it is the check that matters most.

## The stops

Come back to the user only for: a stated constraint you can neither satisfy nor test (say which) · a goal you cannot restate in one sentence after reading its context · a triage call where bounded and architectural both fit and the wrong one is expensive · a criterion only the user can attest (write it `manual`; it binds at build, not here). When the user is present, questions are cheap: one at a time. Everything else is a call you make and write down in `Problem.md`.

## Red flags

| Thought | Reality |
|---|---|
| "I know what they mean; the tests would just restate the design." | The design only shrinks when the tests exist first. Write them. |
| "This one is small; the stage is overkill." | Then it is a spike (free) or bounded (one screen). Skipping the stage is how specs pile up that no test ever checked. |
| "I'll call it a spike." | Reaching for the lighter label to skip the gate is the doubt. Take the heavier path. |
| "Every component has tests." | Observed failure: a background worker's unit tests all passed while it sat unwired, and the feature shipped dead. Where is the `WHOLE-PATH:` criterion? |
| "That's a deployment detail." | Observed failure: "it must keep running without my laptop" was treated as setup, and the architecture that ignored it was caught four hours into installation. A stated requirement is a constraint. |
| "The schema can't say it, so I'll write the nearest thing that validates." | Write the outcome down as a finding in `Problem.md`. Never a weaker criterion. |

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "This criterion can't be met as written; I'll write one that can." | Observed failure: that substitution is how a stage was marked done while its core step still ran a mock. An unmeetable outcome is recorded as unmet, with the reason. |
| "I'll write the tests once the design is clear." | The tests are this stage's exit. `decide` cannot open without them. |
| "It validated, so it's a test." | Observed failure: seven criteria carrying a `<date>` placeholder in their paths validated, the work finished, and not one could ever pass. Each criterion names the change that would make it fail today. |

## Self-check

- Did I say the path out loud, and does the ceremony match it?
- Did the gate exit 0? Its reading of the file, not mine.
- Is every stated requirement under `## Constraints`, verbatim?
- Could every criterion fail today, and can I name the change that makes each true?

Source: Nova Caelum (Apache-2.0). Derived from obra/superpowers `brainstorming` (MIT).
