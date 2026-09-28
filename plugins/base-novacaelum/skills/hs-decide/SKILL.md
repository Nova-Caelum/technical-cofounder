---
name: hs-decide
description: The second stage of the working loop. Use when a run's tests.json has passed the understand gate and the design is still open ("what are our options", "sketch the architecture", "cut this to v1", "how do we build this"). Weighs two or three options against the frozen tests, sketches the chosen one as named components, and cuts every component no test needs unless a declared principle keeps it. If Hyperspace Engine is installed, use its gear* skills instead.
---

# hs-decide: options, architecture, the cut

Generate two or three real options against the frozen tests, sketch the chosen one as named components, and cut every component no test requires, unless cutting it contradicts a principle the project has declared. The cut is a set operation against files that already exist, and so is the rule that stops it.

Observed failure: a first draft of this very loop cut artifact hashing because "no test fails without it". The hashing was what enforced a declared principle (fix, don't quietly pivot), so the cut was reversed. Both halves of the rule, every time.

## The rule

Enter the stage, read the frozen `tests.json` and `Problem.md ## Constraints`, then work through the three references in order: options, architecture, descoping. They write `02_decide/Decision.md`, `Deferred.md`, `mapping.json` and `principles.json`. Leave only through the decide gate.

## When to use

Fires when:
- The last passed gate is `understand` and the next stage is `decide`.
- The user asks "what are our options", "sketch the architecture", "cut this to v1" about a goal whose tests are frozen.
- A run sits at `decide` and its `mapping.json` has not passed the gate.

Does NOT fire for:
- A goal with no frozen `tests.json`: `hs-understand` first.
- The spec, the plan, the tasks: `hs-draft`. Building: `hs-build`.
- Changing a frozen test. That is a double-back to understand, not a design choice.
- A choice outside any run: `option-conception`.

## The process

1. **Enter** (`<python>` is the Python from setup).
   ```
   <python> "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" set-node runs/<slug>/loop.state.json --node decide
   ```
   Number the tests `T1..TN` in file order once; that is the only test vocabulary from here on. Bounded runs: walk the references inline. Architectural: each may go to a fresh subagent, one at a time.
2. **Options.** `references/options.md`. Two or three genuinely different approaches, each weighed against every `T<n>` and every constraint; one chosen, recommendation first, with the reason. When the user is present, one question: accept or override.
3. **Architecture.** `references/architecture.md`. The chosen option as named components: what each does, who uses it, what it depends on, which tests it passes. The names become the mapping's keys.
4. **Descoping.** `references/descoping.md`. Run `overbloat-review` on the sketch (advice, not a verdict), then the two-part cut on every component: (a) no test needs it, and (b) cutting it contradicts no active principle. Writes `mapping.json`, `principles.json` and `Deferred.md`.
5. **Gate.**
   ```
   <python> "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" gate-pass runs/<slug>/loop.state.json --node decide --by <you> --mapping runs/<slug>/02_decide/mapping.json --artifact runs/<slug>/02_decide/Decision.md
   ```
   Exit 0 freezes the mapping, the principles and deferred files it points at, and `Decision.md`. Exit 1 lists every refusal at once.

## What the gate checks

From `mapping.json` alone, with its `tests_file`, `deferred_file` and `principles_file` resolved beside it: every `T1..TN` is referenced by at least one component; every component is kept by a test, kept by a principle that exists in `principles.json` with `state: active`, or bulleted by its exact name under `## Deferred`; no unknown test id, no unknown or inactive principle, no duplicate or nameless component. It cannot tell "needed to pass T3" from "helps with T3". That is the delete test in `descoping.md`.

## The stops

Come back to the user only for: an option that passes the tests only by violating a HARD constraint (say which line) · a component that (a) cuts and (b) keeps, where keeping it costs days rather than lines · a test no option can pass without something the constraints forbid (a double-back to understand, their call) · two options where the wrong pick is a rebuild. Everything else is a call you make and write down in `Decision.md`.

## Red flags

| Thought | Reality |
|---|---|
| "No test needs it, cut it." | That is half the rule. Read `principles.json` before the cut lands. |
| "It's principled, keep it." | Name the principle's id. If you can't, it is not a declared principle, and the gate refuses the id. |
| "I'll sketch the architecture, then map it." | Options are weighed against `T<n>` first; components are named per test. The mapping is not decoration on a finished sketch. |
| "It's marked v2; the section can stay." | A deferred component leaves `## Architecture`. The mapping's kept components are the v1 set. |
| "This maps to a test we'll add later." | There is no such test. An unknown `T<n>` is refused; the honest moves are defer, or go back to understand. |
| "The architecture obviously satisfies the constraints." | One line per constraint, per option, before the decision. "Obviously" is an unverified assumption. |

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "No test needs it, cut it." | Observed failure: that sentence cut a mechanism twice in one project, and both cuts were reversed because the mechanism was what enforced a declared principle. |
| "(b) says it's principled, so keep it." | A keep costs something. Measure it against the value lost, and name the principle or it is not a keep. |
| "The plan names this component, so it exists." | A document's shape is neither a test nor a principle. Decomposition inherited from an outline is the bloat signature. Defer it with that reason. |

## Self-check

- Did the gate exit 0? Its reading of `mapping.json`, not mine.
- Does every option carry a line per constraint, and does `## Decision` say why over the others?
- Is every deferred component gone from `## Architecture` and bulleted by exact name under `## Deferred`?
- Was `overbloat-review` run on the sketch, with enough context to know what the goal is replacing?

Source: Nova Caelum (Apache-2.0). Derived from obra/superpowers `brainstorming` (MIT).
