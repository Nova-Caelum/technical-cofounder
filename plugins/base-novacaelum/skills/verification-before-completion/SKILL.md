---
name: verification-before-completion
description: >
  Invoke this skill whenever an agent is about to claim work is complete,
  fixed, passing, or ready — before committing, creating a PR, shipping a
  deliverable, or handing off. Requires empirical verification of the
  completion claim (running commands for code; walking acceptance criteria
  for non-code deliverables) before making any success assertion. Evidence
  before claims, always. Used by every agent in this plugin — invoke
  whenever any completion claim is about to be made, regardless of agent
  or deliverable type.
---

# Verification Before Completion

## Overview

Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you haven't verified in this message, you cannot claim it passes.

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What evidence proves this claim?
2. RUN / EXERCISE: Execute the verification (fresh, complete)
3. READ: Full output / observed result — check exit code, count failures,
   or walk the artifact against its acceptance criteria
4. VERIFY: Does the evidence confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | Test passes once |
| Agent completed | VCS diff shows changes | Agent reports "success" |
| Requirements met | Line-by-line checklist | Tests passing |
| PRD / plan complete | Line-by-line re-read of acceptance criteria against the draft | "All sections are drafted" |
| Design render ships | Open at target viewport, verify against design intent (screenshot compare, alignment check) | "The code compiled" / "Playwright loaded the page" |
| Audit finding stands | Every finding cites file:line evidence; quote the offending code/config | "The pattern usually means X" |
| Deliverable answers the question | State the original question in one sentence; identify the specific claim/number in the deliverable that answers it | "The analysis is thorough" |
| Workflow / automation works | Trigger end-to-end, observe last-node output or downstream side effect | "The nodes are wired correctly" |

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!", etc.)
- About to commit/push/PR without verification
- Trusting agent success reports
- Relying on partial verification
- Thinking "just this once"
- Tired and wanting work over
- **ANY wording implying success without having run verification**

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ compiler |
| "Agent said success" | Verify independently |
| "I'm tired" | Exhaustion ≠ excuse |
| "Partial check is enough" | Partial proves nothing |
| "Different words so rule doesn't apply" | Spirit over letter |
| "The deliverable isn't code so this rule doesn't apply" | Spirit over letter — verification discipline applies to every completion claim, not just code |

## Escalate When Verification Is Impossible

If a completion claim **cannot** be verified from within the current session — required access is missing, the target system is prod-only, cross-machine state isn't reachable, another agent's tools are needed, or a decisive verification would take longer than ~20 minutes to design — do **not** claim completion.

Surface to the user with three specifics:
1. The exact completion claim you cannot verify
2. What access or environment would resolve it
3. Your recommended next step (hand it to an agent that has the access / defer the claim / narrow the deliverable until it *is* verifiable)

Papering over an unverifiable completion claim is the failure mode this skill exists to prevent.

## Key Patterns

**Tests:**
```
✅ [Run test command] [See: 34/34 pass] "All tests pass"
❌ "Should pass now" / "Looks correct"
```

**Regression tests (TDD Red-Green):**
```
✅ Write → Run (pass) → Revert fix → Run (MUST FAIL) → Restore → Run (pass)
❌ "I've written a regression test" (without red-green verification)
```

**Build:**
```
✅ [Run build] [See: exit 0] "Build passes"
❌ "Linter passed" (linter doesn't check compilation)
```

**Requirements:**
```
✅ Re-read plan → Create checklist → Verify each → Report gaps or completion
❌ "Tests pass, phase complete"
```

**Agent delegation:**
```
✅ Agent reports success → Check VCS diff → Verify changes → Report actual state
❌ Trust agent report
```

## Why This Matters

See `references/` for accumulated failure patterns. Common ones:

- **should-work-without-running** — claim without running; broken code merges
- **trusting-agent-success-reports** — subagent said done; work incomplete
- **partial-check-treated-as-full** — linter clean ≠ build clean
- **assumption-swapped-for-verification** — assumed criteria met; misaligned deliverable ships

## When To Apply

**ALWAYS before:**
- ANY variation of success/completion claims
- ANY expression of satisfaction
- ANY positive statement about work state
- Committing, PR creation, task completion
- Moving to next task
- Delegating to agents
- Shipping any deliverable (code, deck, PRD, render, workflow, analysis)

**Rule applies to:**
- Exact phrases
- Paraphrases and synonyms
- Implications of success
- ANY communication suggesting completion/correctness

## The Bottom Line

**For code:** Run the command. Read the output. Then claim the result.

**For non-code deliverables:** Open the artifact. Walk it against the acceptance criteria. Then claim completion.

Verification is empirical or it isn't verification. This is non-negotiable.

---

Source: Nova Caelum's public no-mistakes plugin, `verification-before-completion` v2.0 (MIT), itself adapted from obra/superpowers `verification-before-completion` (MIT). Copied with its `references/`; light edits for plugin vocabulary, and one internal precedent reworded.
