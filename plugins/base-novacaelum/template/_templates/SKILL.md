---
name: your-skill-name
description: Use when <trigger condition>, <second condition>, or the user says "<phrase they actually use>".
---

<!--
SKILL TEMPLATE
1. Copy this file to .claude/skills/<your-skill-name>/SKILL.md. The folder name must equal `name`.
2. Before you write a word below the frontmatter, run pressure-scenario-skill-authoring:
   three or more observed failures, from two or more sources.
3. Replace every <placeholder>. Delete these comments and any section you don't need,
   except The Rule and the Source line.

The description holds TRIGGERS ONLY, in under about 280 characters. It loads into every
session. When a description summarizes the workflow, agents follow the summary and skip
the body.

This template comes from Nova Caelum's technical-cofounder kit (Apache-2.0).
-->

# <Skill Title>

## Overview

<One to three sentences: what this enforces and why.>

**Core principle:** <the one sentence to remember if nothing else is>

## The Rule

<The rule, imperative, in one paragraph. If an agent reads nothing else, this must be enough.>

## When to Use

Fires when:
- <a concrete, checkable trigger>
- <the phrase a user actually says>

Does NOT fire for:
- <an adjacent case> → use `<other skill or agent>`

## The Process

1. <One action.>
2. <One action.>
3. <One action.>

<!-- More than seven steps means the skill is doing too much. Split it. -->

## Red Flags

If you catch yourself thinking:
- "<the thought that comes right before skipping this>" → <what to do instead>
- "<…>" → <…>

## Common Rationalizations

<!-- Every row cites an observed failure. No observation, no row. -->

| Rationalization | Reality |
|---|---|
| "<the excuse, verbatim>" | <why it's wrong.> Observed failure: <what happened, in one line> |
| "<…>" | <…> |
| "<…>" | <…> |

## Self-Check

Before responding:
- <a question where "no" means stop>?
- <…>?

## Out of scope

- <a case this skill doesn't cover> → `<the skill or agent that does>`

Source: <"original", or the upstream repo and file you adapted> (<license>).
