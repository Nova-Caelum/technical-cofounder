# Triage: the three paths

Classify, then say it out loud before the first question: "this looks bounded, so I'll open a run with a one-screen Problem.md and a short tests.json". That gives the user a chance to override before any work. When in doubt between two, take the heavier one.

| | Spike | Bounded | Architectural |
|---|---|---|---|
| **What it is** | A feasibility question ("can we…", "is it possible…", "quick and dirty is fine") whose output is an answer, not a thing you keep | A well-scoped change to something that already exists and can be read on disk: a flag, a small endpoint, a one-file fix | A new project, subsystem or tool; a change that moves a boundary other things rest on |
| **The test** | Would the deliverable be thrown away once the question is answered? | Can you name the file or flow that changes, and read it now? Knowing the *kind* of thing is not enough | Is there no existing flow to change, or will the change move an interface others depend on? |
| **What it costs** | Nothing. No run, no state file, no Problem.md, no tests.json, no gate | A run · Problem.md of about one screen · a few criteria, at least one executable and one `WHOLE-PATH:` · the gate | A run · Problem.md as long as the constraints need · a full tests.json · the gate · real options at decide |
| **How it ends** | A recommendation in the conversation: the question, what you tried, the answer. Anything built is throwaway | The understand gate, then `hs-decide` (short, for bounded work) | The understand gate, then `hs-decide` with options |

Ceremony scales with the path. The gate does not: at least one non-manual criterion and one `WHOLE-PATH:` criterion, the same for a flag as for a subsystem.

## Why the spike is free

If the lightest path still cost a state file, people would skip the stage and write ad-hoc specs instead. So the spike registers nowhere. Two consequences:

- A spike's follow-up ("the probe worked, keep it") is a new request. Triage it again; it is usually bounded. Throwaway code is not promoted by relabelling it.
- A spike never opened a run, so there is nothing to gate. Don't open one afterwards to "record" it.

## The ratchet is one-way

Hidden complexity found mid-run upgrades the path. Stop, say so, step up:

- **Spike to bounded or architectural:** the answer turned out to be a thing you keep. Open the run now; the probe's findings go under `## Problem`; nothing built is carried in as done.
- **Bounded to architectural:** the "one file" touches a boundary. Re-mark `## Path` with why, widen the constraints and the register, and add the criteria the wider scope needs. If `tests.json` was already frozen, the edit is a double-back and the state file will count it.

Nothing downgrades mid-run. An architectural run that turns out small finishes as a short architectural run.

## Red flags

| Thought | Reality |
|---|---|
| "This is too simple to need tests." | Simple means a short tests.json, not none. Two criteria and a `WHOLE-PATH:` line. |
| "I understand this kind of system, so it's bounded." | Bounded measures what is on disk, not your familiarity. A new project has no existing flow. |
| "It grew, but I'm almost done." | Hidden complexity upgrades the path mid-run. Stop and say so. |
| "They approved the spike, so the follow-up is approved too." | Each request gets its own triage and its own gate. |
| "I'll open a run for the spike just to be safe." | Then it is not a spike. Safe is the heavier path, not heavier ceremony on the lighter one. |

## Three one-liners

- "Can the test runner work inside a git worktree?" **Spike.** Try it, report, throw the scratch away.
- "Add a `--tests` flag to the gate command." **Bounded.** The function exists on disk; one screen of Problem.md, three criteria, one of them `WHOLE-PATH: the gate command with --tests on a valid file exits 0 and the state file shows it frozen`.
- "Build the understand stage." **Architectural.** No existing flow; a new skill with a gate other stages depend on.
