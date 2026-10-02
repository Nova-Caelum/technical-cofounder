---
name: overbloat-review
description: Use when about to add a new agent, skill, hook, MCP server, rule, service, dependency or abstraction layer, or when calling a substantial script, rewrite or refactor finished. Also when someone asks "is this overkill?" or "do we need this?". Advise-only over-engineering audit.
---

# Overbloat Review

An advise-only audit that asks one question of anything you are about to add: **does its structure earn its place?**

## What bloat is

Bloat is structure that reflects how something was built rather than what it does. The diagnostic question is never "is this too long?". It is **"would this shape exist if it were designed once, knowing every requirement?"**

The signature is a worklist, phase plan or review checklist fossilized into the architecture:
- three validation helpers because the spec had three bullets
- one class per phase of the rollout
- a history lesson inside a runtime file, because the build was staged

Length is a symptom, never the metric. Never recommend cutting lines, compressing prose or golfing. Recommend **re-derivation**: given everything we know now, what shape does this take? Either fewer moving parts fall out of the better design or they don't. If they don't, the thing was already lean.

Observed failure: a deploy script roughly doubled, from about 1,000 to 2,000 lines, during a hardening pass while every anti-bloat check stayed quiet. A second model re-derived the same function at about half the size.

## When to use

Fires when:
- You are about to propose or add a new agent, skill, hook, MCP server, rule, command, workflow, service, dependency or abstraction layer.
- You are about to call a substantial piece of implementation finished: a new script, a rewrite, or a hardening, refactor or migration pass. This is the main bloat vector, precisely because it doesn't feel like adding anything.
- Someone asks "is this overkill?" or "do we need this?"

Does NOT fire for:
- Docs, debugging, analysis or a small diff.
- Correctness, security, performance or style. Those go to `engineering-code-review`.
- Whether the goal is worth pursuing at all. That's a planning question.

## The five tags (a closed set; don't add a sixth)

| Tag | Fires when | Evidence required |
|---|---|---|
| `redundant:` | Something that already exists covers it. | The existing thing's path, plus proof it is actually used (step 3). |
| `dormant-risk:` | Its trigger or shape matches things that went unused. | The unused analog, by name or path. |
| `native:` | The platform already does it: Claude Code, the framework, the language or the OS. | A doc link or the feature's name. |
| `yagni:` | It has one user or one use case, or only a hypothetical future one. | "The spec names one use; no other consumer." |
| `shrink:` | A smaller mechanism does the same job with nothing lost. | The smaller mechanism, stated. In structural form, name the borrowed decomposition and the concern it really is. |

`shrink:` has two forms:
- **Surface form:** fewer units. One rule patch is smaller than a new skill.
- **Structural form:** the decomposition mirrors the build sequence or a spec's bullet list rather than the problem's natural shape.

## Procedure

0. **Boundary check.**
   - Is this a new unit of surface, or a substantial implementation at completion? If it's neither, return "out of scope for overbloat-review."
   - Are you being asked to fix it? This skill never edits. Route the fix to whoever builds.
1. **Name the units.** For example: "This adds 1 skill, 1 hook and 1 rule."
2. **Walk the five tags for each unit.** A tag without its evidence doesn't fire.
3. **Verify every "already covered" claim.** A cited existing thing must be active, not nominal. It should show at least one of these:
   - it's referenced from the project's agents, skills, rules or `CLAUDE.md`
   - git log or session history shows recent use or change
   - it's wired into something that runs

   If it exists but nothing uses it, downgrade `redundant:` or `native:` to `dormant-risk:`. The coverage claim is invalid, so judge the proposal on its own merits.
   Observed failure: a proposal was rejected as "already covered" by a skill that had no uses in 30 days. The coverage was nominal.
   Zero uses signals dormancy only if the work that would use it actually came up in that window.
   Observed failure: two design skills with no recent uses were read as a graveyard. No design project had come up at all. The work hadn't been asked for; the skills hadn't been neglected.
4. **Score it, directionally.** For example:
   - `net: -1 skill possible (fold into X)`
   - `net: 0 — proposal stands`
   - no tags fired: `Lean already. Ship.`
5. **Return the report, then stop.** Never edit the artifact. The person who asked decides.

## Output

When findings fire:

```
# overbloat-review
**Artifact:** <one line> · **Reviewed:** <date>

## Findings
<tag>: <observation, one sentence>. <suggested action, one sentence>.

## Score
net: <directional summary>

## Evidence
- <path, link or command output behind each redundant: and native: claim>
```

When nothing fires, the whole report is: `Lean already. Ship.`

Stay under about 250 words. If you spot correctness, security or performance problems on the way, list them at the end as `out-of-scope-observation:` and say where they should go.

## Red flags

If you catch yourself thinking:
- "It's small, it doesn't need a review." → Small additions are how systems bloat, and a small thing gets a small review.
- "Cut it to 200 lines." → That's a line target. Re-derive the shape instead.
- "X already does this." → Did you check that X is used? If not, it's `dormant-risk:`.
- "This case needs a sixth tag." → Run the candidate tag through the five first.
  Observed failure: a proposed sixth tag, run through the taxonomy, was tagged `shrink:` itself, and the set stayed at five.

If the `worklog_append` tool is available, log one line with the artifact, the finding count and the score, tagged `overbloat-review`.

Source: Nova Caelum (Apache-2.0). The closed tag taxonomy, structured output and advise-only stance are adapted from DietrichGebert/ponytail `ponytail-review` (MIT).
