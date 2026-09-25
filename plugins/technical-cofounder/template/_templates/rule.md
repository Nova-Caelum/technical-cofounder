<!--
RULE TEMPLATE
1. Copy this file to .claude/rules/<rule-name>.md. Claude Code loads every file there into
   every session, so each rule is paid for in every conversation. Keep it short.
2. A rule earns its place only if a cheaper fix doesn't exist. In order, try to:
   - delete the problem
   - enforce it with a check (a script, a hook or a test)
   - state it in one sentence in one place
   Write a full rule only when all three fall short.
3. Run pressure-scenario-skill-authoring first. Every rationalization row cites an observed
   failure.
4. Replace every <placeholder> and delete these comments.

This template comes from Nova Caelum's technical-cofounder kit (MIT).
-->

# Rule: <Name>

**Scope:** <who it binds, and when: every session, every commit, every architecture call>

## The rule

<The rule, imperative, in one to three sentences. If an agent reads nothing else, this is enough.>

## Triggers

Invoke this rule when:
- <an observable moment: "about to …", "the user says …">
- <…>

## What this means concretely

**Do:**
- <a concrete behavior>

**Don't:**
- <a concrete behavior>

## Red flags

If you catch yourself thinking:
- "<the thought that comes right before breaking this rule>" → <what to do instead>
- "<…>" → <…>

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "<the excuse, verbatim>" | <why it's wrong.> Observed failure: <what happened, in one line> |
| "<…>" | <…> |
| "<…>" | <…> |

## Self-check

Before responding, ask:
1. <a question where "no" means stop>?
2. <…>?

## Failure this prevents

<One short paragraph naming the failure pattern, so a future reader knows what they'd reintroduce by deleting the rule.>

Source: <"original", or what you adapted it from> (<license>).
