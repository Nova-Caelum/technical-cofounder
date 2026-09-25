# Your Name — Personalization Layer

> Preloaded into context at the start of every session by this plugin's
> SessionStart hook (`hooks/session-preload.sh`).
> Fill this in yourself, or run `/technical-cofounder:onboard` for a
> guided, one-question-at-a-time interview.

---

## Identity

- <what you're building, and your role on it>
- <primary machine / OS — e.g. "Mac, primary daily driver">
- <anything else that shapes how an agent should work with you>

---

## Energy state framework

Declare your state in natural language — not detected, not assumed.
Agents should honor it immediately and hold it until you signal a change.

| State | Signal example | Agent shape |
|---|---|---|
| `sharp` | <e.g. "I'm locked in"> | <e.g. long context ok, surface trade-offs, recommend with rationale> |
| `steady` *(default)* | <no explicit signal> | <balanced: key options, recommend, ship> |
| `tired` | <e.g. "one thing at a time"> | <action over explanation, no "want me to..." offers> |

---

## Decision-style preferences

- <lead with a recommendation, or want 2-3 options first?>
- <how should uncertainty be flagged — say plainly, or hedge?>
- <reversibility bar: at what point should an agent stop and ask before acting?>

---

## Working rhythms

- <timezone, and whether timestamps need conversion when reported to you>
- <batching preference: one big session vs several short ones>
- <checkpoint cadence on long sessions — explicit pauses, or barrel through?>

---

## Derailment detection

- <do you want an agent to flag off-topic drift during a session? at what threshold?>
