---
name: hyperspace
description: Use at the start of any session on a goal that is bigger than a quick fix, and on every resume, before the first action. Routes the work to its stage of the working loop (understand, decide, draft, build, live). Fires on "let's figure out what we're building", "spec this out", "what are our options", "write the plan", "build it", "is this done", "where were we", or any project folder holding a loop.state.json.
---

# Hyperspace: the working loop

An agent cannot decide it is finished. Left alone it declares victory on a stub, marks work complete because it looks complete, and loops at the end of a build without noticing. This loop replaces that judgment with a state file and four gates that read files and refuse on missing evidence.

## The rule

Before you answer, plan, or touch a file, find out which stage the work is in and enter that stage's skill. Say which one fired: "Using hs-decide to weigh the options." Then follow it as written. A stage is the only door into its work; the steps live in the stage, not here.

## The stages

| Stage | Skill | Exits through | Proves |
|---|---|---|---|
| understand | `hs-understand` | the understand gate | `tests.json` defines finished, including one criterion that walks the whole path |
| decide | `hs-decide` | the decide gate | every test maps to a component; every component earns its place |
| draft | `hs-draft` | the draft gate | the plan is tracked work: every task has a criteria file a verifier can close |
| build | `hs-build` | the build gate | every task closed by a verifier-lite verdict, or openly deferred |
| live | `hs-live` | a person's `confirm` | the person ran the acceptance test and said it cleared |

Gates are one way. A stage cannot be entered until the gate before it has passed, and a passing gate freezes its files by sha256. Editing a frozen file later is allowed and is counted as a double-back: the evidence of whether a run is fixing bugs or changing its mind.

## Route the work

Find the run: `find . -name loop.state.json -not -path "*/node_modules/*"`. Read it with the Python from setup (`<python>`):

```
<python> "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" read <run>/loop.state.json
```

| What the state file says | Enter |
|---|---|
| No state file for this goal, and the goal is not yet framed | `hs-understand` |
| `current_node` is a stage whose gate has not passed | that stage's skill: resume it |
| The last passed gate is `understand` | `hs-decide` |
| The last passed gate is `decide` | `hs-draft` |
| The last passed gate is `draft` | `hs-build` |
| `status: live` | `hs-live`. It outranks every row above: a live run never re-enters build on its own |
| `status: done`, `descoped` or `killed` | nothing. The run is over; a new goal is a new run |

Between two stages, enter the earlier one. Hidden complexity moves a run forward into more ceremony; nothing downgrades mid-run. A failure whose cause is already known is debugging, not a stage. A value inside a filed task belongs to build, not to a new run.

Route by the goal's own state file, never by another run's.

## What the scripts answer

Every script call exits `0` passed, `1` refused (fix what it names and run it again), `2` a usage error or an unreadable file, `3` hold (build only: waiting on a person). Read the exit code and the message; never read a refusal as a pass.

## Red flags

| Thought | Reality |
|---|---|
| "This is conversation, not a task." | Questions and clarifications are tasks. The routing check comes before the reply. |
| "It's one small change; the loop is overkill." | Then it is a spike or a bounded run, and `hs-understand` says so in one line. "Overkill" is the tell. Observed failure: five skills sat loaded while five small decisions went past them. |
| "One more attempt first; I'll route if it fails." | The retry is where the stage was needed. Route before the attempt. |
| "I remember where we were." | Read the state file. Memory does not survive a compaction; the file does. |
| "The build looks finished, so I'll say it's done." | Only the build gate confers `live`, and only a person confirms `done`. |
| "The table told me what to do." | The table names doors, never steps. Enter the stage; the stage has the steps. |

## The user's instructions win

The user's instructions override this skill and the stage skills; the skills override default behavior. Skip a stage's workflow only when the user says so explicitly.

Source: Nova Caelum (Apache-2.0). Derived from obra/superpowers `using-superpowers` (MIT).
