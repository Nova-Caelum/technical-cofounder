# Rule: Eliminate-First Discipline

**Status:** Binding

Source: adapted from Nova Caelum's internal agent rules (2026). License: MIT.

---

## The disease

Prose is the default response to a recurring problem. Prose is
unenforced, it bloats over time, and it duplicates. A codebase or
agent-system accumulates "check X when Y" comments and rules that nobody
reads twice.

**Default to deletion before addition. When the reflex is to warn, run the
ladder first.**

---

## The ladder (in priority order — drop a rung only when the higher one doesn't apply)

### Rung 1 — Eliminate

A one-move fix that makes the whole problem class structurally
impossible. Bounded means: closeable now, by your own hand, from a clean
spec, without becoming a project.

- *Anti-procrastination:* if the permanent fix is no bigger than the
  warning you were about to write, the warning is the expensive option.
- *Decision mechanism:* when fix-vs-warn isn't obvious, generate a couple
  of real options before dropping to a lower rung. **Jumping straight to
  Rung 3 or 4 is the primary failure mode this discipline exists to
  prevent** — this step is what prevents it.

### Rung 2 — Enforce by check

Build an executable check, not a readable rule: a script, a test, a
validation step, a linter rule. Something that runs, not something that
has to be remembered.

### Rung 3 — Minimum prose, single location

The fewest words, in one canonical place. Never scatter the same warning
across multiple files.

### Rung 4 — Warning as last resort

Every warning left at this rung should carry a review date. Undated
warnings are permanent debt this discipline does not permit — if it's
worth writing down, it's worth revisiting.

---

## Lexical self-catch triggers

When about to write any of these phrases, stop and run the ladder:

```
TRIPWIRE · remember to · NOTE: · be careful · check X when Y
WARNING: · must … before · IMPORTANT: … before · do NOT forget
```

Each one is a tell that you're about to add Rung 3 or 4 prose when a
higher rung might actually close the problem.

---

## Success metric

Track it, don't just feel it: periodically grep your own project for the
warning-shaped phrases above (`tripwire|remember to|check .* when|NOTE:|be
careful|WARNING:|must .* before|IMPORTANT:.*before|do NOT forget`) across
the files where rules, comments, and instructions live. The count should
trend down over time, net of new additions — if it isn't, the discipline
isn't earning its keep and the form factor needs to change.

---

## What this means concretely

**Do:**
- Ask "can this problem class be made impossible?" before writing a rule
  about it.
- Prefer a script or test that fails loudly over a comment that might be
  read.
- Put a review date on any warning you do write.
- Consolidate duplicate warnings into one canonical location the moment
  you notice them.

**Do not:**
- Write a new "remember to..." comment as the first response to a
  recurring mistake.
- Scatter the same caution across three files "just in case."
- Leave a warning with no date attached — that's how permanent debt
  accumulates.
- Skip the option-generation step and jump straight to a rule, when a
  10-minute fix would close the problem for good.

---

## Known risks

- **Lexical triggers catch a handful of string patterns; paraphrases
  evade them.** The periodic grep sweep is the backstop, not the primary
  defense.
- **The "bounded" gate at Rung 1 is a judgment call.** The
  option-generation step is the mitigation, not a guarantee — it's still
  possible to misjudge what's bounded.
- **Some existing scattered warnings are scar tissue from before this
  discipline existed.** This rule says "don't add new ones" — it doesn't
  demand you retroactively delete everything already in place.

---

## Failure mode this rule prevents

A system that responds to every recurring mistake with a new sentence of
prose ends up governed by hundreds of sentences nobody reads, instead of
a handful of checks that actually run. The ladder forces the cheaper,
more durable fix to be considered first, every time.
