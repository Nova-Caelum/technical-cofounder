---
name: new-agent
description: Use when someone wants a new agent or persona ("make me an agent for X", "we need an agent that…", "should this be its own agent?", "split this agent in two") or is about to write an agent file with nothing behind it. Gate, then spec, then Claude Code creates the file.
---

# New Agent

Decide whether an agent should exist. If it should, specify exactly who it is before anyone writes a line of its system prompt. The gate and the spec are the value here, and writing the file is Claude Code's job.

**Core principle:** an agent that shouldn't exist is cheapest to stop at the gate. An agent that should exist is decided in its spec, not in its prompt.

## The rule

Never write an agent file before the gate has a written verdict. Take the facts you can't infer from the user, not from the nearest similar agent. Those facts are what it's for, what it refuses, and its model and tools. Hand the finished spec to Claude Code's own agent creation, or write `.claude/agents/<name>.md` yourself when asked. Register it, so the team's orchestrator knows it exists. Prove the agent loads and still carries its reason to exist before you call it done.

## The process

1. **Harvest first.** If the conversation already says what the agent is for, use that. Ask only about the gaps, one question at a time.
2. **Intake: a conversation, not a form.** Pin down three things before moving on:
   - **Role:** what it's handed and what it hands back, one line each.
   - **Scope:** at least two things it refuses, and where each goes instead.
   - **Essence:** what "working well" feels like, and the standard it would rather be slow than break.

   Don't proceed until you can state its purpose in one sentence the user recognizes.
3. **Take the cheap facts from the user.** Ask:
   - **Shape:** a *lead* runs as the main session and may delegate; a *specialist* gets called for one job and returns a result.
   - **Model:** usually `inherit`.
   - **Tools:** omit the field to allow everything, or list tools only to restrict it.
   - **Location:** project `.claude/agents/` or user `~/.claude/agents/`.
   - **Who hands it work.**

   If the user is unsure about one, write `DEFERRED` and move on. Never copy a value from a similar agent.
   Observed failure: the user said "task", and the agent filed it as a different type, pattern-completed from a similar earlier item. The nearby example overrode an explicit instruction.
4. **Run the gate, and write the verdict down.** Run `overbloat-review` on the proposal. Then answer the questions below in the spec's Gate section:
   - Does this need a different *identity* (a different standard, different refusals, different authority), or only a different *procedure*? Procedure alone is a skill.
   - Could it be a skill that an existing agent uses? That wins when the tools are already held and the change is a workflow. It loses when the skill would fight its host's character.
   - Could it be a command, a rule, or a line in `CLAUDE.md`?

   The verdict is one of four:
   - `NEW-AGENT`: continue to step 5.
   - `SKILL-ON-<agent>`: stop and route to `pressure-scenario-skill-authoring`, then a skill.
   - `RULE`: stop and write the rule.
   - `NO-BUILD`: stop, and say why. `NO-BUILD` is a good outcome.

   If the gate has never returned anything but `NEW-AGENT`, it isn't really running.
   Observed failure: once a conversation slid from strategy into building, required checks stopped firing because they depended on someone noticing them. The user had to push back twice in one session. A written verdict either exists or it doesn't.
5. **Fill in the spec.** Copy `_templates/agent.md` to `agent-specs/<name>.md` and fill in every section. The `setup` skill (`/base-novacaelum:setup`) puts `_templates/` in the project, so run it if the folder is missing. Budgets are caps, not targets. Every behavior the agent carries should trace to a failure someone has seen. If the agent gets a red-flags or rationalization section, run `pressure-scenario-skill-authoring` first.
6. **Hand off the file creation.** By default, give Claude Code the filled spec and ask it to create the agent:

   > Create a project agent at `.claude/agents/<name>.md` from `agent-specs/<name>.md`. Take the frontmatter from its Frontmatter block and the body from its Body section.

   When the user asks you to write it directly, write `.claude/agents/<name>.md` yourself. Either way, keep the spec: it's the record of why the agent is shaped the way it is.
7. **Register it.** Copy the spec's Registry entry into the registry that sits beside the agents folder the file went into:
   - a project agent in `.claude/agents/` goes in `.claude/registry/agents.json`. If that file doesn't exist yet, create it with the base registry's shape: a `roles` object (copy the base team's, or declare your own) and an `agents` list.
   - an agent you add to a plugin goes in that plugin's `registry/agents.json`.

   Then run the check with the Python from setup and fix what it names: `<python> "${CLAUDE_PLUGIN_ROOT}/registry/check_registry.py" .claude` for a project, or with the plugin's folder in place of `.claude`. If that path doesn't resolve, find `check_registry.py` inside the installed `base-novacaelum` plugin. `technical-cofounder` routes work by reading the registry, so an agent missing from it is one it never hands anything.
8. **Prove it loads and is whole.**
   - The frontmatter has `name` (no `:` in it) and a `description` with "Use when…" triggers.
   - Grep the body for the capability that is its whole reason to exist. Zero hits means stop and fix.
     Observed failure: an agent was one step from install with zero mentions of its signature capability. It would have shipped hollow.
   - In a fresh session, confirm it shows up in `/agents`, or run `claude --agent <name>` and give it one in-role task.

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "They said make it an agent, so running the gate would be obstructive." | The gate is the one check their enthusiasm can't do for them, and it's four lines. The failure in step 4 happened because a check lived in someone's head instead of a file. |
| "The model, tools and shape are obvious from the role." | That's pattern-completion, the failure in step 3. Ask. It costs one question. |
| "The spec is complete, so we're done." | A complete document isn't a decision. Observed failure: six hours, about 2.5M tokens and eight subagents produced plenty of artifacts and zero finished tasks, because the artifacts were counted as progress. The user's yes is the finish line. |
| "I'll write the design up properly once things settle." | Observed failure: a design that lived only in a chat transcript took nearly an hour to recover. The spec file goes on disk first. |
| "Fanning out research subagents will fill the spec faster." | Four or more at once means stating the cost estimate and waiting for a yes. Observed failure: a 16-agent wave spent half a month's quota in fifteen minutes. |

## Self-check

- Can I state the agent's purpose in one sentence the user recognizes?
- Does the spec's Gate section carry a verdict, and could that verdict have been anything but `NEW-AGENT`?
- Did the model, tools and shape come from the user, or did I infer any of them?
- Does the body mention the agent's signature capability?
- Is it in the registry, and does `check_registry.py` pass?
- Did it load, and did it do one task in role?

## Out of scope

- Editing an existing agent: edit its file directly.
- A new skill: `pressure-scenario-skill-authoring`, then `_templates/SKILL.md`.
- Choosing between third-party agent packs: `option-conception` plus `overbloat-review`.

Source: Nova Caelum (Apache-2.0). Merged from its internal agent design, build and install skills, with the spec template adapted from an earlier Nova Caelum client kit.
