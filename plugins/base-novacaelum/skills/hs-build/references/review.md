# REVIEW.md: the person's checklist

Written to `runs/<slug>/REVIEW.md` whenever a task needs a person: an open `manual` criterion, or the build gate's HOLD list. One file, every such task in it. The conversation carries the file's path and the task count, nothing else; the word budget binds the chat, never this file.

Rules for every entry: the task's **title, never its id** · every path **in full** · every command **one line, or a script file** (a multi-line command breaks on paste) · what they are looking for **in plain English**, not what an agent would grep.

---

```markdown
# Review: <run> · <date> · <N> task(s) need you

## 1. <Task title>

- **What was done:** <two or three sentences: what changed, in plain English>
- **What you are checking:** "<the criterion, verbatim>". In practice: <what a pass looks like to a person>
- **Files to look at:**
  - `<full path>`: <what to look for in it>
- **Command to run** (code only): `<one line>`. A pass prints: `<the exact line to expect>`
- **To close it, say:** "<task title>: confirmed". Your words are recorded verbatim.

## 2. <Next task title>

<the same five lines>
```

---

**When they have been through the list:** record each confirmation in that task's `attest.json`, rerun the verifier with `--attest`, and rerun the build gate. Anything that did not pass gets one line on what they saw; it is not fixed from the review.
