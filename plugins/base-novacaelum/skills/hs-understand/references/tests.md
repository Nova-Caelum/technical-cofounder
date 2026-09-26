# Test writing: writing tests.json

Writes the file that defines finished before anything is designed. The understand gate reads it, decide cuts scope against it, draft plans tasks that serve it, and the build closes tasks with the same verifier that can run it.

`runs/<slug>/01_understand/tests.json` is a verifier-lite criteria file:

```json
{
  "id": "<slug>-acceptance",
  "criteria": [
    {"statement": "…", "verification": {"kind": "file_state", "path": "src/app.py", "assertion": "contains", "expected": "def greet"}},
    {"statement": "WHOLE-PATH: …", "verification": {"kind": "command_check", "check_id": "tests", "target": "tests/test_app.py"}},
    {"statement": "…", "verification": {"kind": "manual", "instruction": "…"}}
  ]
}
```

Tests are numbered `T1..TN` by their position in `criteria`, `manual` ones included. Decide and draft refer to them only by those numbers.

## Steps

1. **Trace.** For each line under `## Constraints` and each outcome under `## Problem`, decide: one criterion, several, or none expressible. Each statement names an observable outcome and implies the change that would make it true today. If it is already true, it is not a criterion.
2. **Type each criterion.**
   - `file_state`: `path` relative to the project root (no leading `/` or `~`, no `..`, no `<placeholder>`); `assertion` one of `exists`, `not_exists`, `contains` (with `expected`), `modified_after` (with an ISO-8601 `expected`). Use `exists` only on a path that is absent today; otherwise assert what the work changes, with `contains` or `modified_after`.
   - `command_check`: `check_id` `tests` with a `target` test file (run as `python3 -m unittest <target>` from the project root), `git_diff_nonempty`, or a name defined in the project's `verify.commands.json`. Anything else comes back `uncertain`.
   - `manual`: an `instruction` a person can follow. Only for what only a person can attest; it binds at build and live, not here. Keep it, and add an executable criterion beside it.
3. **The whole-path criterion.** At least one statement begins `WHOLE-PATH:`, literally, first thing in the string. Shape: `WHOLE-PATH: <the entry action> → <the terminal observable effect>`. It is the criterion that fails when any component between them is disconnected. Prefer an executable check: a test that drives the path end to end. Unit tests on components never satisfy it.
4. **Report what the format refuses.** An outcome no kind can express, a path outside the project, a check that needs a service: write it under `## Schema findings` in `Problem.md`, with how a person or tool would check it. Never rewrite a criterion into the nearest thing that validates.
5. **Hand back** to the stage for the gate. Don't run `gate-pass` yourself from here.

## Self-review

- [ ] For every criterion I can name the change that makes it true today and the change that would make it fail again. No statement admits two readings.
- [ ] No `<` or `>` in any path or target.
- [ ] No `exists` on a path that is present now; no `not_exists` on one absent now.
- [ ] The `WHOLE-PATH:` criterion fails if any single component between entry and effect is disconnected, not only if one is broken.
- [ ] Every constraint is traced to a criterion or a schema finding; no criterion was softened to avoid one.
- [ ] The set fits one goal. A set that needs decomposition goes back to `problem.md` step 3.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "Every component has its own tests, so the thing is tested." | Observed failure: a worker's unit tests all passed while it sat unwired. One `WHOLE-PATH:` criterion is required, and the gate refuses its absence. |
| "It validated, so it's a test." | Observed failure: seven criteria with a `<date>` placeholder in their paths validated, and none could ever be true. Validation is the floor. |
| "The format can't say it, so I'll write something close that validates." | A reported gap is the most useful thing this step can return. A smoothed one is invisible. |

Source: Nova Caelum (Apache-2.0). Derived from obra/superpowers `brainstorming` (MIT).
