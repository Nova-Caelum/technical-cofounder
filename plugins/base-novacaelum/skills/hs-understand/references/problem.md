# Problem depth: writing Problem.md

Turns the verbatim ask into a one-screen statement of what is actually being solved, for whom, under which stated constraints, with every load-bearing assumption checked before a design exists to rest on it. `tests.md` reads this file to write criteria; `hs-decide` checks every option against its `## Constraints`.

Write `runs/<slug>/01_understand/Problem.md` with these sections, in this order:

1. **`## Ask (verbatim)`**: copy `original_input.md` unchanged. Beneath it, restate the goal in one sentence. If you cannot, after reading the ask and the context it names, stop and say what is missing. A guess here is the most expensive sentence in the run.
2. **`## Path`**: `bounded` or `architectural`, and one line on why (from triage). If what you learn below argues for the heavier path, say so at the top of this section and step up. Never down.
3. **`## Problem`**: the real problem and for whom. Explore before asking: the files the ask names, recent commits, earlier notes. Then ask, one question per message, multiple choice where the options are known: purpose, constraints, success. A request that names several independent subsystems is decomposed here into the first sub-goal and a list of the rest; the run proceeds on the first.
4. **`## Constraints`**: every stated requirement, verbatim, each marked `HARD`. Where a thing runs, who can reach it, what it may cost, what it must not depend on: these are constraints, not setup details, however casually they were said. A constraint you can neither satisfy nor test is written down as `UNSATISFIABLE: <why>` and is a stop, not a silent drop.
5. **`## Assumptions Register`**: one row per assumption the goal rests on (tool behavior, environment, access, what the existing code already does). Use `assumption-check` if it is installed; otherwise fill the table by hand. Verify every low-confidence, load-bearing row before this file is done: documentation first, then a minimal test. Reasoning is not verification. A load-bearing row you cannot verify from here is a stop.

   | Assumption | Confidence | Load-bearing | Verified via | Actual behavior |
   |---|---|---|---|---|

6. **`## Out of scope`**: what the goal is not, and the sub-goals deferred in step 3. Nothing here may come back at decide without an edit to this file, which the state file counts as a double-back once frozen.
7. **`## Schema findings`**: appended by `tests.md`. Write `none` if nothing was refused.

Size it to the path: bounded is about one screen; architectural is as long as the constraints need and no longer.

## Self-review

- [ ] No `TBD`, no `<…>`, no "to be confirmed" in the constraints or the register.
- [ ] Every line under `## Constraints` is a quotation I can point at.
- [ ] Every load-bearing register row says how it was verified, not that it was.
- [ ] `## Out of scope` is not empty. An empty one says the goal has no edge, which is never true.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "That's a deployment detail, not a requirement." | Observed failure: a requirement stated plainly at kickoff was treated as a setup detail, the assumption check never ran, and the mismatch surfaced four hours into installation. |
| "I know what they mean; I'll write the problem from the design in my head." | A problem written from the design has the design's defects one file earlier. |
| "The assumptions are obvious; I'll list them without checking." | Observed failure: a documentation-sourced conclusion sat on record for a day before a twenty-minute test refuted it. A table typed from memory is a list of hopes with a header. |

Source: Nova Caelum (MIT). Derived from obra/superpowers `brainstorming` (MIT).
