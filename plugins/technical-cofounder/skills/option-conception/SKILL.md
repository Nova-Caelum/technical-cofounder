---
name: option-conception
description: Use when a choice is on the table and only one approach is in view ("what should we do here?", "is there a better way?", "how would you approach this?", "give me options"), or when you notice you're already building out the first idea you had.
---

# Option Conception

Produce two or three genuinely different approaches to whatever is on the table. Weigh each against the stated constraints, then recommend one first, with the reason. It happens in the conversation, and there's no artifact unless someone asks for one.

## The rule

Before committing to an approach, produce at least one you didn't think of first. Weigh every candidate against every stated constraint. Lead with a recommendation whose reason names constraints, not taste.

## When to use

Fires when:
- A choice is on the table and only one approach is in view. That covers architecture, technology, direction, tool selection and the shape of a deliverable.
- The user asks "what should we do here?", "is there a better way?" or "give me options".
- You notice you're already drafting, specifying or picking values for your first idea. The alternative is owed before the draft, not after it.
- An earlier call is being reopened because its first framing turned out wrong.

Does NOT fire for:
- A choice the user has already made. Their call is the answer: carry it out, then disagree out loud if you disagree.
- The working loop's decide step (`gear3-decide`), which weighs options against frozen tests and owns this there.

## The process

1. **Write down the constraints.** Use what the user or the task actually stated, such as budget, deadline, scope, platform or "it has to work offline". Mark any constraint you inferred rather than heard as inferred.
2. **Generate two or three approaches with different shapes, not one shape at two sizes.** If option B is option A with a knob turned, you have one option. Apply YAGNI to each one now: anything no constraint requires comes out before you write it down.
3. **Weigh every option against every constraint.** Give one line per constraint per option: satisfies, violates or unknown. For each unknown, say what would settle it. An option that violates a hard constraint is struck through and kept, along with the line that killed it. It's evidence that the space was searched.
4. **Recommend first, then say why not the others.** Give the pick and its reason in a paragraph, and one line for each of the rest. "Cleaner" and "more elegant" don't carry a decision. This is a recommendation, not a gate, so never block on a reversible choice.
5. **Check what the recommendation rests on.** If it clears a constraint only because a tool or platform is assumed to behave a certain way, verify that before you recommend (`assumption-check`). If only one approach survives honest generation, say so and explain why. Don't pad the list with an option nobody would build.

Shape of the answer:

```
Constraints: C1 … · C2 … · C3 … (inferred)

A: <shape>. C1 satisfies · C2 satisfies · C3 unknown (a quick probe of X settles it)
B: <shape>. C1 satisfies · C2 violates (<why>) · C3 satisfies
~~C: <shape>~~. Struck: violates C1 (<why>)

Recommend A: <reason, in constraint terms>. Not B, because <line>. Flip cost: <what switching later costs>.
```

## Red flags

| Thought | Reality |
|---|---|
| "The replacement covers this, so repointing to it is enough." | Observed failure: two routes were repointed to a successor skill without anyone reading its "does not fire for" list. It declined exactly those cases, so both routes pointed at something that would never run. Read what you route to before you route to it. |
| "The first read is the read. I already know what this is." | Observed failure: a zero-usage count was read as proof that two skills were dead. The kind of work that would use them simply hadn't come up yet. The first framing is the anchor, not the answer, and a differently framed second option is the check on it. |
| "We're past the design conversation. This is just picking values." | Observed failure: required checks stopped firing once a strategy conversation slid into hands-on value-picking, and the user had to push back twice in one session. The value-pick is where the unexamined alternative bites. |

Source: Nova Caelum (Apache-2.0). Derived from obra/superpowers `brainstorming` (MIT).
