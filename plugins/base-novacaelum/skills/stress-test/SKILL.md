---
name: stress-test
description: Use when the user wants a plan, design or decision pressure-tested before committing, as in "stress test this", "grill me", "poke holes in this", "what am I missing?", "challenge this" or "sanity check this plan".
---

# Stress Test

Interview the user relentlessly about every part of the plan until you both reach a shared understanding. Walk down each branch of the decision tree, and resolve the dependencies between decisions one at a time.

## Rules

1. **One question at a time.** Never stack questions. Wait for the answer before you ask the next one.
2. **Bring your recommended answer** with every question, so the user reacts to a proposal instead of generating one from scratch. Often they'll just say yes.
3. **Look before you ask.** If the code, docs, config or project history can answer a question, read them instead of asking.
4. **Follow the dependencies.** Settle the decisions that others hang on first, so early answers shape later questions.
5. **Probe the usual weak points:**
   - **Scope:** does this belong to something else?
   - **Dependencies:** what must exist before it works?
   - **Ownership:** who builds it, and who checks it?
   - **Failure:** what happens when it breaks, and how would anyone know?
   - **Scale:** does it hold at ten times the users, data or team?
   - **State:** what gets created, changed or read, and where does it live?
   - **Cost:** money, time and upkeep.
   - **Reversibility:** how hard is it to undo?
6. **No softballs.** If the plan has a weak point, name it directly. Honesty beats comfort.
7. **Close each branch** with a one-sentence decision before moving to the next.

## Wrap-up

When every branch is resolved, give:
- **Decisions reached:** a numbered list.
- **Open questions:** anything deferred or unresolved, with what would settle each one.
- **Recommended next step:** write the spec, run `option-conception` on a branch that stayed thin, hand the plan to `engineer`, or investigate a named unknown.

## Don't

- Start it unasked. Offering a stress test is fine; springing one on someone isn't.
- Reopen a decision that has already been made and shipped unless the user reopens it.
- Let a vague answer close a branch. Rephrase the question once, then record it as an open question.

Source: Nova Caelum (MIT). Adapted from mattpocock/skills `grill-me` (MIT).
