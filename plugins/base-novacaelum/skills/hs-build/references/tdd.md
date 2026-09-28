# Test first: RED, then GREEN

Makes a task's change provable before it is claimed: one failing test observed for the right reason, then the smallest change that turns it green, both pasted into the report. Those two sections are the evidence the build stage checks before it runs the verifier.

## Steps

1. **Read the criteria.** For each `command_check` and `file_state` criterion, write one line naming the production change that would make it true, before touching code.
2. **RED.** Write one test for one behavior the task demands: a name that says the behavior, real code under test, mocks only when unavoidable. Run the explicit target (`<python> -m unittest tests/test_x.py`, with the Python from setup; never a bare discovery run). Paste the output under `## RED`. It must fail for the expected reason: the feature is missing, not a typo or an import error. If it passes immediately, you are testing behavior that already exists: fix the test. If it errors, fix the error and run it again until it fails correctly.
3. **GREEN.** Write the smallest change that passes. No extra options, no neighboring refactors, nothing the test did not ask for. Run the same target again and paste it under `## GREEN`. Any other test in the target that went red, fix now.
4. **Refactor** only while green, running it again after.
5. **Repeat** per criterion, then run every target the brief lists once more and paste the summary line.
6. Leave no scratch files. Don't commit unless the brief says to.

## Rules

- No production code without a test that failed first. Code written before its test is deleted and written again from the test, not kept "as reference".
- Never `git stash`, `git checkout --` or any tree-wide revert to stage a clean RED on a shared tree: it lifts other people's edits. Capture RED by running the target before your change.
- The task's criteria are not yours to change. A criterion that can't be met goes back as `NEEDS_CONTEXT`.

## Self-review

- [ ] For each test, I can name the production change that would make it fail again.
- [ ] `## RED` shows a failure whose message matches the missing feature, not an error.
- [ ] The GREEN diff contains nothing the test didn't ask for.
- [ ] Every command in the report names an explicit test file.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "Tests written after achieve the same thing." | A test written after passes immediately and proves nothing about its power to fail. RED is the evidence it tests the right thing. |
| "I ran the tests; a status word is enough." | Pasted output is evidence; a status word is a claim. |
| "The work is done; the criteria will sort themselves out." | The verifier runs the criteria as written. Read them first. |

Source: Nova Caelum (Apache-2.0). Derived from obra/superpowers `test-driven-development` (MIT).
