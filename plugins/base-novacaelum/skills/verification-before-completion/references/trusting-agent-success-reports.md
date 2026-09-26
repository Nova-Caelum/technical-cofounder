# Pattern: Trusting Agent Success Reports

## Claim
"Subagent reported success — task complete."

## Skipped
Reading the subagent's actual output, VCS diff, or produced files.

## Damage
- Subagent wrote incomplete or wrong code / content
- Sometimes fabricated a success signal that wasn't backed by real work
- Caught days later when downstream work exposes the gap
- Full rework, plus meta-rework: the parent agent's confidence in delegation is now suspect

## Why It Happens
Delegating feels like the work is done. It isn't — the delegation is done. The work exists in the child's output, which requires independent verification.

## Antidote
When a subagent reports success:
1. Check the VCS diff — what actually changed?
2. Read the produced files — do they match spec?
3. Run any verification the child was supposed to run
4. Only then propagate the completion claim upstream

The rule is exactly the same as for your own work — evidence over report.
