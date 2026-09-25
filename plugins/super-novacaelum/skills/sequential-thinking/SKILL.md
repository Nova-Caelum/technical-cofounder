---
name: sequential-thinking
description: >
  Use the Sequential Thinking MCP tool effectively for complex, multi-step problems.
  Triggers when: planning multi-phase implementations, debugging with uncertain root cause,
  exploring design alternatives, breaking down ambiguous requirements, or any task where
  the full scope isn't clear upfront. Teaches revision, branching, and dynamic thought
  extension (needsMoreThoughts) to avoid linear-only usage patterns.
---

# Sequential Thinking — Full Feature Usage

The Sequential Thinking MCP tool (`mcp__sequential-thinking__sequentialthinking`) supports structured problem-solving with **revision**, **branching**, and **dynamic extension**. Most agents use it linearly only. This skill teaches the full feature set.

---

## Schema (camelCase)

| Parameter | Type | Purpose |
|-----------|------|---------|
| `thought` | string | The current thinking step content |
| `thoughtNumber` | number | Current position in sequence (1-indexed) |
| `totalThoughts` | number | Estimated total steps (can increase via `needsMoreThoughts`) |
| `nextThoughtNeeded` | boolean | `true` if more thinking required, `false` when complete |
| `isRevision` | boolean | `true` if this thought revises a previous one |
| `revisesThought` | number | Which thought number is being revised |
| `branchFromThought` | number | Which thought to branch from |
| `branchId` | string | Identifier for this branch (e.g., "alt-approach", "subtask-auth") |
| `needsMoreThoughts` | boolean | `true` when `totalThoughts` was underestimated mid-sequence |

---

## When to Use Revision (`isRevision: true`)

Revise a previous thought when:

1. **New information contradicts earlier reasoning**
   - You assumed X, but evidence now shows Y
   - A constraint you didn't know about invalidates a prior step

2. **Better understanding emerges**
   - Initial analysis was shallow; deeper investigation reveals nuance
   - You realize a prior thought missed a critical consideration

3. **Revisiting for context in long sequences**
   - Thought 12 needs to reference and update conclusions from Thought 3
   - Earlier reasoning needs to be synthesized with later findings

**Usage:**
```json
{
  "thought": "Revising my earlier assumption about auth flow...",
  "thoughtNumber": 8,
  "totalThoughts": 12,
  "isRevision": true,
  "revisesThought": 3,
  "nextThoughtNeeded": true
}
```

---

## When to Use Branching (`branchFromThought`, `branchId`)

Branch when:

1. **Handling subtasks before returning to main flow**
   - Main task needs a sub-investigation that would clutter the primary sequence
   - "Let me explore this authentication edge case, then return to the main implementation"

2. **Exploring alternative approaches under uncertainty**
   - Two viable solutions exist; branch to evaluate each
   - "Branch A: microservice approach. Branch B: monolith approach."

3. **Investigating side questions that support the main objective**
   - A tangential question arises that needs resolution before continuing
   - "Before I can design the API, I need to branch and clarify the data model"

4. **Breaking down complex problems into manageable parts**
   - The problem is too large for a single linear sequence
   - Create branches for each major subsystem, then synthesize

**Usage:**
```json
{
  "thought": "Exploring alternative: what if we use event sourcing instead?",
  "thoughtNumber": 6,
  "totalThoughts": 10,
  "branchFromThought": 4,
  "branchId": "alt-event-sourcing",
  "nextThoughtNeeded": true
}
```

**Return to main branch** by not specifying `branchId` in subsequent thoughts after the branch investigation completes.

---

## When to Use `needsMoreThoughts`

Use when **mid-sequence, you realize `totalThoughts` was underestimated**:

1. **Problem turned out more complex than initially scoped**
   - Started with `totalThoughts: 5`, now at thought 4 and clearly need 8+

2. **New requirements or constraints emerged**
   - Scope expanded during investigation

3. **Branch created additional necessary steps**
   - Branching added thoughts that weren't in the original estimate

**Usage:**
```json
{
  "thought": "This is more complex than expected. The auth system has three subsystems I didn't account for...",
  "thoughtNumber": 4,
  "totalThoughts": 8,
  "needsMoreThoughts": true,
  "nextThoughtNeeded": true
}
```

Then continue with updated `totalThoughts` in subsequent calls.

---

## Anti-Pattern: Linear-Only Usage

**Wrong:** Using Sequential Thinking as a simple numbered list without revision or branching.

```json
// Thought 1: "First, I'll read the file"
// Thought 2: "Next, I'll parse it"
// Thought 3: "Then, I'll transform it"
// ...
```

This wastes the tool's capabilities. If your thoughts never revise, never branch, and never extend — you're using it as a glorified to-do list.

**Right:** Use revision when assumptions break, branch when exploring alternatives, extend when scope grows.

---

## Integration with Task Planning

When using Sequential Thinking for implementation planning:

1. **Initial estimate** — Set `totalThoughts` based on perceived complexity
2. **Branch for subsystems** — Each major component gets its own branch
3. **Revise as you learn** — Update earlier conclusions when new info emerges
4. **Extend when needed** — Don't force completion; use `needsMoreThoughts`
5. **Synthesize** — Final thoughts should integrate findings from all branches

---

## Example: Debugging with Full Features

```
Thought 1: "Initial hypothesis: the bug is in the API layer"
Thought 2: "Testing API... responses look correct. Revising hypothesis."
Thought 3 (isRevision=true, revisesThought=1): "Bug is NOT in API. Moving to data layer."
Thought 4: "Data layer shows inconsistent state. Branching to investigate two possibilities."
Thought 5 (branchId="cache-issue"): "Branch A: Could be stale cache."
Thought 6 (branchId="race-condition"): "Branch B: Could be race condition in writes."
Thought 7 (branchId="cache-issue"): "Cache invalidation looks correct. Ruling out."
Thought 8 (branchId="race-condition"): "Found it — write operations lack locking."
Thought 9: "Synthesizing: Root cause is race condition. Fix: add mutex to write path."
Thought 10 (needsMoreThoughts=true): "Need to verify fix doesn't introduce deadlocks..."
```

---

Source: Nova Caelum (MIT). Copied verbatim from the Nova Caelum `no-mistakes` public repository (github.com/Nova-Caelum/no-mistakes), used under the MIT License — see THIRD_PARTY_NOTICES.md.
