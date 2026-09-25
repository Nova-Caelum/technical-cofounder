# The spec: PRD.md

Renders the frozen decision for a reader who has opened nothing else. It designs nothing: every component, cut and principle in it already exists in `02_decide/`.

Create `runs/<slug>/03_draft/PRD.md` with exactly these sections, in this order, each with content:

1. **Header.** `# PRD: <slug>`, then one line: the acceptance set's path and the first eight characters of its sha256, so a reader can tell which version it describes.
2. **`## Acceptance set`**: `T1..TN`, one line each: `T<n> <kind>: <statement, verbatim>`. Verbatim, because a paraphrase is a second copy that drifts. Mark the `WHOLE-PATH:` entry and every `manual` entry.
3. **`## What we are building`**: one page at most (bounded runs: one screen). The goal in one sentence, the option taken and its reason in a paragraph naming the tests and constraints it cites, then every constraint verbatim, marked HARD.
4. **`## Components`**: one entry per kept component in `mapping.json`, in mapping order, name verbatim: **Does**, **Used by**, **Depends on** (condensed from `## Architecture`), **Passes** `T<n>…`, **Kept by** test or principle `<id>`. Nothing the mapping lacks; nothing from `## Deferred`. Close with the data flow: the `WHOLE-PATH:` criterion walked through the named components.
5. **`## Principles`**: one bullet per principle cited in the mapping: `**<id>**: <statement>. Keeps: <components>. <why cutting would contradict it>`. If none is cited, one line saying so and how many active principles the file held. The section's presence proves the check ran.
6. **`## v2 recap`**: the `## Deferred` bullets, one line each: `**<name>**: <what it is>. Reopen when: <the clause, verbatim>`. No reasoning. A future reader uses this to rebuild the v2 list and nothing else. Close with `v1 set: <component names>`.
7. **`## Decisions inherited`**: a table of what this spec rests on and does not re-argue: every constraint, every verified assumption, the decision and who made it, every ruling the spec depends on. Cite, never re-derive.
8. **`## Not claimed`**: what v1 does not deliver, from `## Out of scope` and the deferred set, including the uncomfortable line. A spec that claims everything is the one that ships a mock as done.
9. **`## Closeout: rules enforced only by prose`**: every rule this document states that no script, gate or test enforces, one line each: `<the rule>: enforced by prose only; harden by: <the check that would, or unknown>`. If there are none, write `None found. Every rule above names its mechanism.` and mean it.

## Self-review

Run once, with fresh eyes, and fix inline. No second pass, no reviewer.

- [ ] Acceptance-set statements are byte-equal to `tests.json`.
- [ ] `## Components` names equal the mapping's kept components, no more, no fewer.
- [ ] `## v2 recap` carries no reasoning clause.
- [ ] No `TBD`, `TODO` or `<…>` anywhere.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "The PRD is where the architecture gets written properly." | Observed failure: a spec shipped a v2-shaped architecture with a v1 label, because the cut happened in its acceptance section and nowhere else. |
| "Principles and deferrals are recorded elsewhere." | That is the context that gets lost between sessions. They are required sections. |

Source: Nova Caelum (MIT). Derived from obra/superpowers `writing-plans` (MIT).
