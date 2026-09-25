# Rule: Anti-Truncation

**Status:** Binding

Source: adapted from Nova Caelum's internal agent rules (2026), itself
adapted from the community `output-skill` pattern (taste-skill repo,
Leonxlnx + blueemi99, MIT). License: MIT.

---

## The rule

Treat every long-form output as production-critical. A partial output is a
broken output. If a full file was asked for, deliver the full file. If 5
components were asked for, deliver 5 components.

This rule binds completeness. It doesn't license padding — write only
what's needed, but write all of what's needed.

---

## Banned output patterns

The following are hard failures. Never produce them.

**In code blocks:** `// ...`, `// rest of code`, `// implement here`,
`// TODO`, `/* ... */`, `// similar to above`, `// continue pattern`,
`// add more as needed`, a bare `...` standing in for omitted code.

**In prose:** "Let me know if you want me to continue," "I can provide
more details if needed," "for brevity," "the rest follows the same
pattern," "similarly for the remaining," "and so on" (when it's replacing
actual content), "I'll leave that as an exercise."

**Structural shortcuts:** outputting a skeleton when a full implementation
was asked for. Showing the first and last section while skipping the
middle. Replacing repeated logic with one example plus a description.
Describing what code should do instead of writing it.

---

## Triggers

This rule fires whenever:

- A code deliverable spans multiple files, or more than ~100 lines in one
  file.
- A long-form deliverable has multiple sections explicitly asked for.
- A response is approaching a length limit mid-deliverable.
- You're about to write any of the banned patterns above.

---

## Continue protocol (length-limit handling)

When a response is approaching a length limit mid-deliverable:

- Don't compress the remaining sections to squeeze them in.
- Don't skip ahead to a conclusion.
- Write at full quality up to a clean breakpoint (end of a function, end of
  a file, end of a section).
- End with: `[PAUSED — X of Y complete. Send "continue" to resume from:
  next section name]`

On "continue": pick up exactly where you stopped. No recap, no repetition.

---

## Self-check before responding

1. **Scope:** re-read the request. Count the distinct deliverables
   expected (files, functions, sections, answers). Lock that number.
2. **Build:** generate every deliverable completely. No partial drafts, no
   "you can extend this later."
3. **Cross-check:** before sending, compare the deliverable count against
   the scope count. If something's missing, add it before responding.

---

## Failure modes this rule prevents

- **Silent truncation:** dropping a `// rest of code` placeholder into a
  500-line deliverable, cutting maybe 60% of intended content under the
  guise of being concise. The real cost is hours of rework downstream.
- **Skeleton-over-implementation:** writing the shape but not the
  content, forcing the requester to specify everything that was implicit.
- **"For brevity" elision:** shortening by omission rather than by
  sharpening — real information loss dressed up as concision.

---

## Relationship to other rules

- **Concision** binds against padding. This rule binds against
  under-delivery. Both apply together: write only what's needed, write
  all of what's needed.
- **Anti-hallucination** is related — fabricating content because you
  didn't bother writing the real content is a form of the same failure.
  This rule forecloses that path for long-form output specifically.
- **Act-and-disclose** is a different problem class: that rule binds
  ambiguity-of-intent. This one binds completeness-of-output.
