# Descoping: mapping.json, principles.json, Deferred.md

Applies the two-part cut to every component in `## Architecture`. A component is cut to v2 when **(a)** no frozen test needs it **and (b)** cutting it contradicts no principle the project has declared. Principles live in a plain local file, so (b) is a lookup, not a feeling.

Write these, in order:

1. **`principles.json`.** The project's declared principles:
   ```json
   {"principles": [{"id": "stdlib-only", "statement": "Ship with the standard library and nothing else.", "state": "active"}]}
   ```
   A principle can keep a component only while its `state` is `active`. If the project has a standing principles file, point `principles_file` at it instead of copying it; the gate freezes whatever the mapping points at. No principles is legal: `{"principles": []}`. Never invent one mid-cut to rescue a component; a principle worth keeping is declared on its own, then cited.
2. **Run `overbloat-review`** on `## Architecture`, and paste its output under `Deferred.md ## Overbloat review`. Its tags point at what to examine first. It never cuts anything by itself.
3. **(a), the delete test.** For each component, list the `T<n>` ids that *fail if it is deleted*: not the ones it helps with. Where this disagrees with the sketch's `Passes` line, the delete test wins. A non-empty list means **kept by test**.
4. **(b), for the rest.** For each component with an empty (a) list: does cutting it contradict an active principle? Name the principle's `id` and write one sentence on what the principle commits the project to and why the cut breaks it. Record it under `Deferred.md ## Kept by principle` as `- **<name>**, `<principle id>`: <the sentence>`. A sentence that names no id keeps nothing.
5. **Defer the rest.** Every component with empty (a) and empty (b) is bulleted under `Deferred.md ## Deferred` as `- **<exact component name>**: (a) no test: checked T1..TN; (b) no principle contradicted; reopen when: <what would pull it back>`. The bold text must equal the component name exactly; the gate matches strings. Replace its `###` block in `## Architecture` with `### <name>, deferred → Deferred.md`.
6. **`mapping.json`.**
   ```json
   {
     "tests_file": "../01_understand/tests.json",
     "deferred_file": "Deferred.md",
     "principles_file": "principles.json",
     "components": [{"name": "<### name>", "tests": ["T1"], "principles": []}]
   }
   ```
   Paths are relative to the mapping's own folder. One entry per `###` in `## Architecture`, deferred ones included with empty lists, so the gate can see they were judged. Then check every `T1..TN` appears in some kept component's `tests`. A test no kept component passes means the sketch is short a component (go back to architecture) or the test is unmeetable (a stop).
7. **`## Mapping` and `## Cuts`** in `Decision.md`: a table mirroring `mapping.json` (component, tests, principles, status), then the deferred count, the kept-by-principle count, and the overbloat summary line.

## Self-review

- [ ] Every mapping name equals a `###` heading; every deferred name equals its bullet.
- [ ] Every cited principle is in `principles.json` with `state: active`. I checked the state, not just the id.
- [ ] No component was kept because it "feels principled".
- [ ] No deferred component still has a live `###` block.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "No test needs it, cut it." | Observed failure: part (a) said cut, the cut landed, and the rule the component enforced was left intact and unenforceable. It was un-cut. Run (b) on every (a) cut. |
| "(b) says it's principled, so keep it." | A quick fix that grows into sessions of work is a common failure. A keep names an active principle and the sentence. |
| "It's marked v2; the section can stay." | Observed failure: a spec cut its scope in the acceptance section and nowhere else, and shipped a v2-shaped design with a v1 label. |
| "The sketch is lean; skip the overbloat review." | The review is cheap, and its findings are exactly the plan-inherited components this step misses by eye. |

Source: Nova Caelum (MIT). The two-part cut rule is Nova Caelum's own; `overbloat-review` is called, not adapted.
