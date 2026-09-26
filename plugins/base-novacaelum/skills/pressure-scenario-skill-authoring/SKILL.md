---
name: pressure-scenario-skill-authoring
description: Use before writing a new skill, rule or agent that shapes how an agent behaves under pressure ("write a skill for X", "add a rule so it stops doing Y", or a red-flags or rationalization section). Collect three or more observed failures first.
---

# Pressure-Scenario Skill Authoring

Skills written from intuition read as rigorous and then fail to fire under pressure, because the excuses they answer are imagined. This skill makes you collect real failures before you write anything.

**Iron law:** no skill without a failing test first. Here, that means three or more observed failures before any prose.

## Step 0: before any frontmatter, body or trigger

### 1. Define the pressure scenario

Write two or three sentences that recreate the conditions where the skill should fire. Use real pressure, not "the user is in a hurry":
- **Time:** "It's late, the demo is tomorrow, and the check costs twenty minutes nobody has."
- **Sunk cost:** "We're three turns down this path, and switching feels wasteful."
- **Authority:** "The user said 'just do it', but the rule says stop and ask."
- **Too small to matter:** "The task is so small that the discipline feels like overkill."

### 2. Gather at least three observed failures from at least two sources

| Source | How |
|---|---|
| Session transcripts | `grep -rh "<phrase>" ~/.claude/projects/` shows what agents actually typed |
| Git history and reviews | `git log -S "<text>"`, reverted commits, PR comments, "fix: undo…" |
| The project worklog | `worklog_search` on the `cofounder` MCP server, or the `worklog/` notes |
| Issues and postmortems | What broke, and the reasoning that led there |

The test: can you quote it? A failure paraphrased to fit your idea is intuition wearing observation's clothes.

### 3. Extract the verbatim rationalization

For each failure, record the excuse the agent gave itself, or the one the postmortem reconstructed, word for word. Save them to `<skill-name>-baseline.md`, with four entries per failure:
- the source
- the pattern
- the verbatim quote
- the row of the skill that answers it

### 4. Only then write the skill

Start from `_templates/SKILL.md`. Answer every captured rationalization by name, either in a Common Rationalizations table (excuse → reality) or a Red Flags list. No row goes in without an observation behind it, and prose that answers no observed failure comes out.

### 5. Match the form to the failure

| Observed failure | Right form | Wrong form |
|---|---|---|
| Knows the rule, skips it under pressure | Prohibition, rationalization table and red flags | Soft guidance ("consider…") |
| Complies, but the output has the wrong shape | A positive recipe that states what the output IS | A list of don'ts |
| Leaves out a required element | A required slot in a template | Reminders in prose |
| The right behavior depends on context | A condition on something observable | An unconditional rule with exemptions |

### 6. Re-test with the skill loaded (recommended)

Run the same scenario in a fresh session with the skill present. Every new excuse becomes a new row. Ship when the re-test turns up nothing new.

## Anti-gaming

The ritual fails the moment it goes pro forma. Watch for:
- **Trivial scenarios.** "What if they're busy" isn't pressure.
- **Paraphrased rationalizations.** "The agent thought it could skip the check" is not what it typed. Find the sentence it typed.
- **Rows that match what you would have written anyway.** Real observation turns up inconvenient rows you wouldn't have guessed. If the derived rows are identical to your intuition, you gamed it.
  Observed failure: the first real run of this ritual derived four rows from actual incidents, and they diverged from the six intuited rows on every point that mattered.
- **One source for everything.** One incident proves one incident, not a pattern.

## When to skip

- An edit to an existing skill that adds no rationalization row.
- Pure reformatting or renaming.
- A problem with no failure history yet, such as a brand-new domain. Say so in the skill's Source line and proceed.

## Boundaries

- Whether the skill should exist at all is a question for `overbloat-review`.
- Whether a tool behaves the way the skill assumes is a question for `assumption-check`.
- Don't skip because "the failure is obvious". Nobody rationalizes around obvious failures. The ones agents skip under pressure come with plausible excuses.

Source: Nova Caelum (Apache-2.0). Adapted from obra/superpowers `writing-skills` (MIT), including its iron law and its practice of matching the form to the failure.
