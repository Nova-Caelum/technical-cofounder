---
name: hs-live
description: The last stage of the working loop, and not a building stage. Use when a run's loop.state.json reads status live, when the build gate has just exited 0, or when the user says "we're live", "run the acceptance test", "sign this off", "is this done yet", "did the test pass". Stops building, hands the person the acceptance test written at the start, and waits for their verdict.
---

# hs-live: the person's test

The stage between finished software and a finished run. Build ends when the machinery says so (the build gate exits 0 and sets `status: live`), not when you decide you're finished. What remains is not work. It is the person running, in a real workflow, the acceptance test the run wrote for itself at the start, while you watch.

Observed failure: a run was built, merged, deployed and verified, and its build stage kept absorbing work for two more days: three defects found and routed, two follow-ups filed, every one real, not one of them the run's goal. Endless loops at the end of a build are the failure this stage exists to end.

## The rule

Stop building. Announce. Hand the person the acceptance test from the start of the run. Then wait: run nothing until they say so, and when they do, run only the test. Bugs found now are the test working, not failing. Classify each: a blocking bug stops the test, gets a real fix done properly, and the test restarts from the beginning; everything else gets one line and the test keeps moving. Triage happens once, at the end, on the whole list. The exit is `confirm`, which the script refuses from anyone but a person.

`live` is an announcement, not a victory claim. Only the person's `confirm` makes it `done`.

## When to use

Fires when:
- `loop.state.json` reads `status: live`. Read it; never infer it.
- The build gate has just exited 0.
- The user says "we're live", "run the acceptance test", "sign this off", "is this done yet".

Does NOT fire for:
- Any task still open, or a build gate that exited 1 or 3: `hs-build`. The status is the predicate, and the script sets it.
- A defect serious enough to invalidate the build: say so, name it, and let the user decide whether the run goes back to build. That is their call.
- A new goal that surfaced during the test: its own run, from `hs-understand`.

## The process

1. **Read the state.**
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" read runs/<slug>/loop.state.json
   ```
   Confirm `status: live` in the file. Do not proceed on a status you reasoned your way to.
2. **Stop.** No edits, no subagents, no merges, no deploys. Add one ledger line: `Live: build closed at <gate time>, <N> tasks closed by verdict.`
3. **Recover the acceptance test.** It is the run's own `01_understand/tests.json`, frozen at the understand gate, plus any `manual` criterion still open. Quote it. Don't restate it, improve it, or swap in what you now think the test should have been. If the frozen test no longer matches what was built, that mismatch is the finding: say it plainly and let the user judge it.
4. **Announce, in one screen.** What is live · where it is live (the commit and, if deployed, the deploy, each checked by reading it back, not by a status message) · the acceptance test, verbatim, as steps the person performs · what you will watch · what a clean pass means. Nothing in it says the test passed.
5. **Wait, then run only the test.** The person decides when the test runs. Until then, run nothing: no setup, no warm-up, no "quick check that it still works".
6. **Classify every finding; fix almost none.** Ask one question of each: can the test continue without this?
   - **Blocking:** stop the test and show the person what you saw. On their go, fix it properly, the real fix, never a bandage to get moving again. Then rerun the test from the beginning: a blocking fix invalidates everything the test showed before it.
   - **Non-blocking:** one ledger line (what, where, what you saw), and carry on. Don't diagnose it, size it, fix it or file it yet.
7. **Triage once, at the end.** Put the whole list in front of the person and decide each: fix now · defer to v2 · not a bug. Anything "fix now" is a new run, entered at its own stage, not more work inside this one.
8. **Exit.** When the person says the test cleared, record their grant, then confirm:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" record-approval runs/<slug>/loop.state.json --human-present true --authority human
   python3 "${CLAUDE_PLUGIN_ROOT}/bin/loop_state.py" confirm runs/<slug>/loop.state.json --by "<the person>" --escaped <N> --caught <M>
   ```
   `record-approval` writes down a grant they already gave; run it only after their word, never to manufacture one. `escaped` is defects their test found that the loop's own tests missed; `caught` is defects the loop's tests caught first. `confirm` writes `status: done` and the escape rate.

## The grade

A clean pass (the frozen test achieved in a real workflow with no troubleshooting, no patch, no "one small fix first") is the best result this loop produces. A test that ran end to end with small findings triaged at the close is the ordinary good outcome. A run that needed three repairs before its test cleared also reaches `done`, and it is not the same grade. Say which one happened.

## The exit

`confirm` refuses any status other than `live` (a run that never passed the build gate can't be confirmed) and any driver whose authority is not `human`. There is no gate for `live`: it is a stage you sit in, not one you pass.

## Red flags

| Thought | Reality |
|---|---|
| "This one is real and it will only take a minute." | It is real, and it is a line in the list. Real findings fixed mid-test are how two days disappear. |
| "I reproduced their test and it passed." | You ran a proxy. Their test is theirs. |
| "I'll run it now so the result is ready when they ask." | They didn't say run it. A result without its driver isn't their test. |
| "A quick patch gets the test moving again." | A bandage on a blocker buys a test result about the bandage. Fix it properly or not at all. |
| "The fix was late in the test, so I only need to re-test from there." | The fix changed what the earlier steps exercised. Start over. |
| "I should fix it before they see it." | They are testing what was built. Hiding a defect corrupts the only real signal this stage produces. |
| "Nothing is happening, so I should find something useful to do." | Nothing happening is the best grade. Idle is what success looks like here. |
| "They said it looks good; that's the sign-off." | `confirm` needs their word on the test, not on the announcement. Ask plainly. |

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "Routing this defect is the disciplined thing to do." | Writing it down is. Fixing it is build, and build is closed. |
| "Stopping means declaring done, and I can't verify done." | You aren't declaring it. `live` says only that building stopped. |
| "I can grade the run myself; the evidence is right here." | `confirm` refuses non-human authority in code. The refusal is the design. |
| "The frozen test is worse than what I'd write now." | Say so, as the finding. Rewriting it now destroys the one comparison the run was built to make. |
| "The deploy reported success, so it's live." | A status message isn't a read-back. Observed failure: green status, nothing changed, five times in one night. |

## Self-check

Before the announcement: does the state file read `status: live`? Is everything I changed merged and, if deployed, read back? Is the test I'm handing over the frozen one, quoted?

Before `confirm`: did the person say the test cleared, not just that the work looks good? Is every finding either written down or an explicit "none"?

Source: Nova Caelum (MIT).
