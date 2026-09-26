# Pattern: Should-Work-Without-Running

## Claim
"Fix is in, tests should pass now."

## Skipped
Actually running the test suite after the fix.

## Damage
- Broken build merged into the main branch
- Downstream agents blocked waiting on green CI
- User discovers the break, says "I don't believe you"
- Trust erodes; subsequent claims are scrutinized more heavily
- Rework cost multiplies: fix the fix, re-verify, re-communicate

## Why It Happens
The fix "looked right" — the reasoning felt airtight. Reasoning is hypothesis; a green test suite is verification. Never let the former substitute for the latter.

## Antidote
Before claiming a fix works, run the exact test that failed. Read the output. Cite the pass in the claim: *"Fix applied; test_foo now passes (was failing on line 42)."*
