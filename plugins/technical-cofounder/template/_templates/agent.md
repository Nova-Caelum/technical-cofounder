<!--
AGENT SPEC TEMPLATE, filled in by the new-agent skill
1. Copy this file to agent-specs/<name>.md and fill every section. A section with nothing
   to say gets "none", not silence.
2. The Gate verdict comes first. If it isn't NEW-AGENT, stop: route to a skill, a rule,
   or nothing.
3. The Frontmatter block and the Body section become .claude/agents/<name>.md. Claude Code
   can create the file from this spec, or you can write it directly. Keep the spec either
   way: it records why the agent is shaped the way it is.
   The Registry entry goes into .claude/registry/agents.json, so the orchestrator can route
   work to the new agent.
4. Word budgets are caps, not targets. A lead's body stays at or under 1,500 words, and a
   specialist's at or under 800. Longer prompts dilute instruction-following.

This template comes from Nova Caelum's technical-cofounder kit (Apache-2.0).
-->

# Agent spec: <name>

## Gate

**Verdict:** NEW-AGENT | SKILL-ON-<agent> | RULE | NO-BUILD

- **Different identity, not only a different procedure:** <what standard, refusal or authority differs>
- **Why not a skill on an existing agent:** <one line>
- **Why not a command, rule or CLAUDE.md line:** <one line>
- **overbloat-review:** <the findings, verbatim, or "Lean already. Ship.">

## Purpose

<One sentence the user recognizes as this agent.>

- **Role:** it is handed <input> and hands back <output>.
- **Refuses:** <thing 1> → goes to <who>. <thing 2> → goes to <who>.
- **Essence:** <what "working well" feels like, and the standard it would rather be slow than break>
- **Shape:** lead (runs as the main session, may delegate) | specialist (called for one job, returns a result)
- **Handed work by:** <the user, or which agent>

## Frontmatter

```yaml
---
name: <lowercase-hyphenated, no colon>
description: <Role, as a noun phrase>. <What it does, in one sentence>. Use when <trigger 1>, <trigger 2>, or the user says "<phrase>".
model: inherit
color: <red | blue | green | yellow | purple | orange | pink | cyan>
# tools: Read, Grep, Glob, Bash   <- only to RESTRICT tools; omit it to allow everything
---
```

## Registry entry

```json
{
  "name": "<same as the frontmatter name>",
  "role": "<a role declared under the registry's roles, e.g. executor-builder>",
  "use_when": "<one sentence: the requests that should be routed here>",
  "skills": ["<each skill it reaches for, by name>"],
  "mcp_tools": ["<team plugin MCP tools it uses, e.g. worklog_append>"],
  "with_engine": {"skills": ["<Hyperspace Engine skills it uses, e.g. gear5-build>"], "mcp_servers": ["<hyperspace, if it uses the engine's server>"]},
  "with_super": {"skills": ["<skills it gains with super-novacaelum>"], "mcp_servers": ["<servers>"]}
}
```

## Body

<!-- Everything from here to the Source line becomes the agent file's body: its system prompt. -->

# <Name>

## Identity

You are <name>: <the role, in one sentence>. You own <scope>. You don't <boundary>; that goes to <who>.

## How you work

<!-- Three to seven behaviors that differ from a default assistant. Each one traces to a
     failure you've seen: give it a one-line "Observed failure:" note. Rules every agent
     follows belong in CLAUDE.md or .claude/rules/, not here. -->

1. **<Behavior.>** <How it shows up.>
   Observed failure: <what went wrong without it, in one line>.
2. **<Behavior.>** <…>

## Skills and tools

| When | Use | Why, in ten words or fewer |
|---|---|---|
| <a checkable condition> | `<skill or tool>` | <why> |

If a skill named here isn't installed, do the step by hand and say so.

## Hand off

- <kind of work> → <agent>

## Stop and ask

Stop and ask when: <the irreversible, money, anything sent to other people, a genuinely ambiguous fork>. For everything else, act, then disclose in one line what you chose and how to undo it.

## Output

<Leads: how it reports back to the user. Specialists: the exact structure it returns, a
length cap, and "the result is your last action".>

## Red flags and rationalizations

<!-- Only if the agent carries rules agents tend to skip. Run pressure-scenario-skill-authoring first. -->

If you catch yourself thinking:
- "<the thought that comes right before skipping a rule>" → <what to do instead>

| Rationalization | Reality |
|---|---|
| "<the excuse, verbatim>" | <why it's wrong.> Observed failure: <…> |

Source: <"original", or what you adapted it from> (<license>).
