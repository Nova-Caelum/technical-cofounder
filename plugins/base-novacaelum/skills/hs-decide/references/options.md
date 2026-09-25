# Options: Decision.md, `## Options` and `## Decision`

Turns a frozen test set and a constraints list into two or three genuinely different ways to pass the tests, each weighed line by line, and one chosen with its reason. The architecture step sketches only the chosen option, so a wrong choice here is the most expensive sentence at decide.

Create `runs/<slug>/02_decide/Decision.md`:

1. **Header.** `# Decision: <slug>`, then one line: the tests as `T1..TN` from `01_understand/tests.json`, each with the first clause of its statement, so a reader never has to open the file.
2. **`## Options`.** Two or three approaches with different shapes, not one shape with a knob turned. For each `### Option <letter>: <name>`:
   - one paragraph describing the shape;
   - a line per test: `passes`, `passes with <named component>`, or `cannot pass: <why>`;
   - a line per `## Constraints` entry: `satisfies`, `violates`, or `unknown: <what would settle it>`;
   - trade-offs: what it costs, what it forecloses;
   - YAGNI applied: every feature no test needs is removed before you write the option down.

   An option that violates a HARD constraint is struck through and kept, with the line that killed it. It is evidence that the space was searched.
3. **`## Decision`.** Open with the recommended option and the reason in one paragraph, then one line for why not each of the others. The reason names tests and constraints. "Cleaner" and "more elegant" don't carry a decision.
4. **Check what the choice rests on.** If the recommended option passes a test or meets a constraint only because a tool or platform is assumed to behave some way, verify that before recommending: docs, then a minimal probe. Record it as a register row under `## Decision`.
5. **Decide.** User present: one question, accept or override, with your recommendation stated; record the answer verbatim. User absent: the recommendation is the decision; write `Decided by: <driver>, user absent` so it is on the record.

## Self-review

- [ ] The options are different shapes, and I can name the test each handles worst.
- [ ] Every `T<n>` and every constraint has a verdict under every option.
- [ ] `## Decision` cites test ids and constraint lines.
- [ ] No `TBD`, no `unknown` left unresolved on the chosen option.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "I know which option we'll take; the others are ceremony." | A second option graded against the tests is the only evidence the first isn't just the one you thought of first. |
| "This option passes once we add a criterion for it." | The tests are frozen. A criterion added now is a double-back to understand. Say so and stop. |
| "The architecture obviously satisfies the constraints." | Observed failure: a deployment requirement nobody checked against the chosen architecture was found four hours into installation. One line per constraint. |

Source: Nova Caelum (MIT). Derived from obra/superpowers `brainstorming` (MIT).
