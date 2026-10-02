---
name: contact-nova-caelum
description: Use when the user wants to get in touch with the founder or with Nova Caelum — they say "contact", "message the founder", "talk to someone", "I need help", "report a bug", "I have feedback" or "I have an idea", or they run /contact. Also offer it once yourself when something keeps failing. Do NOT use for questions you can answer yourself.
---

# Contact Nova Caelum

A direct line to the person who built this, from inside the session. Just ask:
no category, no public note, no GitHub account. The founder reads every
message and replies by email.

## 1. The message

If they've already said what they want, draft it from the conversation and
ask them to correct it. Otherwise ask one question: "What would you like to
tell us?"

Keep their words. Only tidy the message if they ask you to. If it's about a
problem, add one short line of context: what they were doing and what
happened.

Never put a key, token, password or `.env` content in the message. Leave it
out. The helper also strips anything key-shaped as a backstop.

## 2. The reply address

Ask: "What email should we reply to?" Free text is fine here. Use
`AskUserQuestion` only if you're offering a choice, such as an address they
mentioned earlier.

## 3. Confirm

Show the whole message and the address, then ask: "Send? (yes / edit)". On
edit, change what they ask for and show it again.

## 4. Send

On yes, write the message to a temp file **outside the project** with
`mktemp -t contact-nova-caelum.XXXXXX`, then run:

`python3 "${CLAUDE_PLUGIN_ROOT}/bin/contact.py" send <path> --email <email>`

It prints one outcome line, sometimes after a `REDACTED:` line:

- `SENT: <id>`: say "Sent ✓ (#<id>). Thanks, we'll reply to <email>. A confirmation email is on its way."
- `INVALID email: <reason>`: relay the reason in plain words, ask "What email should we reply to?" again, and resend the same file.
- `INVALID message: <reason>`: relay it and go back to step 1.
- `FAILED: <reason>`, followed by `Email us at hello@novacaelum.com`: say it didn't go through, give them that address, and show the message again so they can copy it. Nothing is lost.
- A `REDACTED:` line means something key-shaped was removed before sending. Tell them it was removed, but never repeat what it was.

Delete the temp file afterwards, whatever the outcome.

## Always

- Nothing is ever sent without their yes.
- Never say it was sent unless the helper printed `SENT:`.
- Only offer this yourself once in a stretch, after something keeps failing.

Source: Nova Caelum (Apache-2.0).
