---
name: engineering-architecture
description: Use when making or documenting a technical decision (a technology choice, build vs. buy, a vendor comparison, a system design, a data model, an API pattern), or when asked "should we use X or Y?", "how should we structure this?", or for an ADR or tech evaluation.
---

# Engineering Architecture

A decision is only as useful as its record. Decisions nobody wrote down get relitigated, forgotten or silently violated. This skill makes every significant decision leave a short, durable record behind.

## 1. Size the decision

- **Significant, so write a full ADR:** a technology choice, the infrastructure approach, the data model, an API pattern, auth, a third-party integration, or anything that crosses components or is hard to reverse.
- **Minor, so a one-line note will do:** a config value, a library version, or a naming choice with no architectural reach.

When unsure, write the ADR. Documenting a minor decision is cheap. Leaving a significant one undocumented isn't.

## 2. Check the assumptions first

Before comparing options, list what the decision assumes about how a tool, API or platform behaves. Verify each load-bearing one with a docs quote or a one-minute probe; `assumption-check` does this if it's installed. Vendor docs are a hypothesis until a test agrees.

Observed failure: a stated requirement, that the system keep running without the owner's laptop, was treated as a setup detail. The architecture that ignored it was caught four hours into installation.

## 3. Weigh the options

- **Drivers.** Decide which qualities matter most here: latency, scale, cost, time to value, security or reversibility. Also list the hard constraints.
- **At least two real options.** A decision with no alternative is a default. If only one comes to mind, run `option-conception`.
- **Trade-offs, explicitly.** For each option, say what it buys and what it costs. Everything is a trade-off.

## 4. Write the ADR

Save it where the project keeps decisions (check first), or as `docs/adr/YYYY-MM-DD-short-title.md`.

```markdown
# <Decision title>

**Status:** Proposed | Accepted | Deprecated | Superseded by <link>
**Date:** YYYY-MM-DD · **Deciders:** <who>

## Context
<The forces at play: the problem, why it matters now, the constraints. Neutral.>

## Decision drivers
- <most important quality attribute>
- <second>
- <hard constraints>

## Options considered
### A: <name>
- Pro: <specific advantage>
- Con: <specific cost>

### B: <name>
- Pro: …
- Con: …

## Decision
<Active voice, one or two sentences. "We will use X.">

## Rationale
<Why this option over the others, in terms of the drivers.>

## Consequences
- Enables: …
- Accepted costs: …
- Risks, and how we'll catch them: …

## Assumptions
| Assumption | Load-bearing? | Verified how | What actually happens |
|---|---|---|---|
```

| Need | Record |
|---|---|
| Technology choice, build vs. buy, vendor comparison | A full ADR, with cost in the options |
| A new service or subsystem | An ADR plus a short data-flow sketch |
| Roadmap or sequencing | A short narrative that cites the relevant ADRs |

## 5. Hand off

The ADR anchors the spec; it isn't the implementation. Point the builder (`engineer`) at it along with acceptance criteria. When the decision is expensive to reverse, ask `cto` for an independent review. If `worklog_append` is available, log one line naming the decision and the ADR's path.

## Red flags

- "There's only one sensible option." → Then naming the second one costs a minute. Do it.
- "The docs say it works that way." → That's a hypothesis. Test it before the design rests on it.
- "We'll write it up once it's built." → By then the rejected options and the reasons for rejecting them are gone. Write the ADR now.

Source: Nova Caelum (MIT). The ADR layout is modelled on the public MADR format.
