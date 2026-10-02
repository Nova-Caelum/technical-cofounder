---
name: assumption-check
description: >
  Invoke this skill BEFORE making any load-bearing assertion, recommendation, or decision
  that rests on unverified external information — whether how a tool/API/framework/platform
  behaves, specific facts, numbers, or dates you are about to cite, current versions or
  pricing, or subject-matter details that may be wrong or out of date. Do not wait until
  something breaks — trigger when the task involves: expert recommendations in a specialized
  domain, citing figures or benchmarks, designing permission or auth systems, planning API
  integrations, evaluating tools for adoption, or building any system where a config, SDK
  behavior, or factual claim is load-bearing. Also trigger when: making a placement or
  scope decision, choosing a format or convention, deciding build-vs-buy, or any decision
  where 'I assume X works like Y' or 'I recall X is Y' is the justification. Widely used
  whenever a decision rests on unverified external state or assertions - behavior, facts,
  or expertise.
---

# Assumption Check — Validate Before You Build

The failure pattern this skill prevents: design a system around assumed behavior → discover the assumption was wrong → rework the architecture. The cost is hours. The prevention is minutes.

An assumption is anything you haven't confirmed via documentation or direct empirical test in this specific context. Reasoning ("it probably works this way") is hypothesis formation, not verification. Test environment conditions — session modes, feature flags, environment variables — require the same verification discipline as tool behavior itself.

---

## Proactive mode (start of design session)

Use this when running the check before design work begins. This is the preferred path.

### 1. Surface assumptions explicitly

List every assumption being made about external behavior. Be specific:

> "I assume `allow` in settings.json acts as a whitelist" — unverified
> "I assume this API paginates by default" — unverified
> "I assume the test session has no special modes active" — unverified

If you're struggling to find assumptions, look for: default behaviors, edge cases in configuration, implicit limits, behaviors mentioned in tutorials but absent from reference docs, and conditions about the environment itself (not just the tool).

### 2. Classify by confidence and load

For each assumption:
- **Confidence**: high / medium / low
- **Load-bearing**: does the design break or produce incorrect results if this assumption is wrong?

Focus verification on **low-confidence + load-bearing** first. High-confidence assumptions about stable documented behavior can proceed with a note.

### 3. Verify

For each unverified load-bearing assumption, verify before continuing:

**Documentation first.** Find the specific section — a direct quote or link, not just the homepage. Ambiguous or missing docs means the assumption is unverified.

**Empirical test second.** When docs are unclear, write a minimal isolated test. Minimal means: one command, one config change, one API call — readable output in under a minute. If it requires scaffolding to test, that's a signal the assumption deserves more weight in the design. 

**Web search as fallback.** Community-confirmed examples are weaker than docs or direct tests — note this distinction in the register.

Do not substitute reasoning for verification. Reasoning forms hypotheses. Documentation and confirmed community examples constitute **validation** (acceptable when load-bearing risk is bounded); only empirical tests in the actual target context constitute **full verification** (required when load-bearing risk is high).

### 4. Document and proceed

Record verified behavior — including surprises where actual behavior differed from assumption. Then proceed, referencing verified behavior explicitly in design documents.

If any load-bearing assumptions remain unverified: label them as known risks before continuing.

### 5. Escalate when verification is impossible from-session

If a load-bearing assumption **cannot** be verified from within the current session — required access is missing, the target system is prod-only, cross-machine state isn't reachable, another agent's tools are needed, or a decisive test would take longer than ~20 minutes to design — do **not** proceed with the design.

Surface to the user with three specifics:
1. The exact unverified assumption
2. What access or environment would resolve it
3. Your recommended next step (hand it to an agent that has the access / defer the decision / narrow the assumption until it *is* testable)

Papering over an unverifiable load-bearing assumption is the failure mode this skill exists to prevent. **Precedent:** a docs-sourced assumption-check conclusion sat in the worklog for a day before a 20-minute empirical test refuted it. The test cost minutes. Building the next phase on the wrong architecture would have cost days.

---

## Retroactive mode (mid-design or post-incident)

Use this when the check is running after design work has already begun, or after a failure.

1. List the assumptions the design is currently resting on — trace back through decisions already made
2. Identify which ones were never explicitly verified
3. Verify them now and note whether the current design is still sound
4. Flag any that invalidate design decisions already in place

Retroactive checks often reveal that the design is fine — but the verification gap becomes documented knowledge rather than silent risk.

---

## Assumptions Register

Include this in any ADR, architecture doc, or technical spec. For small decisions (quick config changes, single-file edits), a brief inline note suffices.

```
## Assumptions Register
| Assumption | Confidence | Load-bearing | Verified via | Actual behavior |
|---|---|---|---|---|
| [tool] behaves as [X] | low | yes | [docs link or test output] | [what it actually does] |
```

**Why this matters across sessions:** Populated registers become institutional memory. They explain why the design is shaped the way it is and transfer cleanly across agent handoffs — the next agent inherits verified knowledge, not assumptions. They're also the first place to look when behavior changes unexpectedly.

---

Source: Nova Caelum's public no-mistakes plugin, `assumption-check` v2.0 (MIT). Copied with light edits: plugin vocabulary, and an internal precedent reworded.
