# Your Name — Personalization Layer

> Preloaded into context at the start of every session by the team plugin's
> SessionStart hook (`hooks/session-preload.sh`).
> Fill this in yourself, or run `/technical-cofounder-setup:start` and say
> "continue setup" for a guided, one-question-at-a-time interview.

---

## Identity

- <what you're building, and your role on it, or "not decided yet: starting with a test drive">
- <primary machine / OS — e.g. "Mac, primary daily driver">
- Where you run your agents: <desktop app, command line (CLI), or both>
- <anything else that shapes how an agent should work with you>

---

## Energy state

`steady` is the default. Say another state in plain words at any time; agents
switch at once and hold it until you change it.

| State | How you might say it | How agents work |
|---|---|---|
| `sharp` | "I'm locked in" | Longer context is fine; surface the trade-offs; recommend with the reasoning. |
| `steady` *(default)* | nothing needed | The key options, a recommendation with a short why, then do it. |
| `tired` | "one thing at a time" | Action over explanation, one step at a time, no "want me to..." offers. |

---

## How agents answer you (default)

- Give options with a recommendation and a short why, and say plainly when uncertain.
- <reversibility bar: at what point should an agent stop and ask before acting?>

---

## Working rhythms

- <timezone, and whether timestamps need conversion when reported to you>
- <batching preference: one big session vs several short ones>
- <checkpoint cadence on long sessions — explicit pauses, or barrel through?>

---

## Derailment detection

- <do you want an agent to flag off-topic drift during a session? at what threshold?>
