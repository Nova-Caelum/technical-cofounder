# The plan: workplan.json and the criteria files

The plan is the filing. Each task is a row the build stage will close through verifier-lite, one at a time, so every task carries its own criteria file. The reader of every task is a fresh implementer with no history: a task must stand alone.

## workplan.json

```json
{
  "tests_file": "../01_understand/tests.json",
  "tasks": [
    {
      "id": "greeting-file",
      "title": "Add greeting.txt holding the greeting",
      "summary": "Create the text file the command will print.",
      "owner": "engineer",
      "serves": ["T1"],
      "produces": ["greeting.txt"],
      "blocked_by": [],
      "size": "under an hour",
      "note": "Why it is shaped this way, and the trap to avoid.",
      "criteria": "criteria/greeting-file.json"
    }
  ]
}
```

- **`id`**: unique, `[A-Za-z0-9_.-]` only. It is also the criteria file's `id`, the verdict file's name, and the line in `RECONCILIATION.md`.
- **`title`**: an imperative sentence. **`summary`**: one or two sentences of plain English, readable with no other document open: no test codes, no section references.
- **`owner`**: who builds it (usually `engineer`).
- **`serves`**: the `T<n>` codes this task discharges. Codes live here so the summary can stay plain. Every `T1..TN` is served by at least one task.
- **`produces`**: every file the task creates or changes, by its decided path. Never "the thing it makes".
- **`blocked_by`**: task ids that must close first. Order tasks by it.
- **`size`**: an honest estimate. A task bigger than one working session says so here.
- **`note`**: the reasoning and the trap.
- **`criteria`**: the task's criteria file, relative to the workplan.

The gate reads `id`, `serves`, `criteria` and `tests_file`. The other fields are for the implementer, and the self-review is what keeps them honest.

## The criteria files

`03_draft/criteria/<id>.json`, in the verifier-lite format (see `hs-understand`'s `references/tests.md` for the kinds):

```json
{"id": "greeting-file", "criteria": [
  {"statement": "greeting.txt holds Hello, world", "verification": {"kind": "file_state", "path": "greeting.txt", "assertion": "contains", "expected": "Hello, world"}}
]}
```

- The `id` equals the task id.
- At least one criterion is not `manual`. A person's attestation rides on the task whose work it judges; it is never a task of its own.
- Each criterion is false today and names what the task changes. No `exists` on a path already present; no `<placeholder>` in a path.
- A task that serves a `WHOLE-PATH:` test carries a criterion that walks that path, usually the same end-to-end test.

## Right-sizing

A task is the smallest unit that carries its own criteria and is worth a verdict. Fold setup, configuration and docs into the task whose deliverable needs them. Split only where a verifier could refuse one task and pass its neighbor. Step-by-step code belongs to build (`hs-build`'s `references/tdd.md`), not to the plan.

## Self-review

Run once, with fresh eyes, and fix inline. No second pass, no reviewer.

- [ ] **Coverage:** walk the acceptance set; for each `T<n>`, point at the task whose `serves` carries it.
- [ ] **Placeholders:** no `TBD`, "implement later", "similar to the task above", "add error handling"; no `<…>` in any path.
- [ ] **Names:** every file, component and interface name a later task uses matches the task that produces it and matches `## Components`.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "I'll give the manual check its own task." | An all-manual task can never be closed by a verifier; the gate refuses it. |
| "The criteria can be loose; the tests will catch it." | The criteria file is what closes the task. A loose one closes it without the work. |
| "The implementer will know which files." | They weren't in the conversation. `produces` names each one. |

Source: Nova Caelum (MIT). Derived from obra/superpowers `writing-plans` (MIT).
