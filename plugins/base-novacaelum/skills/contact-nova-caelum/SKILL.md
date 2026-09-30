---
name: contact-nova-caelum
description: Use when the user wants to get in touch with the founder or with Nova Caelum — they say "contact", "message the founder", "talk to someone", "I need help", "report a bug", "I have feedback" or "I have an idea", or they run /contact. Also offer it once yourself when something keeps failing. Do NOT use for questions you can answer yourself.
---

# Contact Nova Caelum

A direct line to the person who built this, from inside the session.

## Step 1: ask how, right away

As your very first action, before any other words, ask with the
`AskUserQuestion` tool. If that tool isn't available, ask the same thing in
chat, as two numbered options.

- **Question:** "How would you like to reach Nova Caelum?"
- **Header:** "Contact"
- **Option 1:** "Message our team directly (Recommended)"
  - Description: "Opens WhatsApp with your message ready to send. The founder reads every message and replies to you there."
- **Option 2:** "Leave a public note"
  - Description: "Posted on our public GitHub page. We read every note, but can't promise a reply."

## Step 2: the message

Before you ask, check whether they've already said what they want. If they
have, draft it from the conversation and ask them to correct it. If they
haven't, ask one question: "What would you like to say?"

Keep their words. Only tidy the message if they ask you to. If the message
is about a problem, add one short line of context, such as what they were
doing and what happened.

Never put a key, token, password or `.env` content in the message. Leave it
out; don't plan to trim it later.

## Route 1: WhatsApp (the founder replies)

1. Show the message and ask: "Send this to the founder on WhatsApp? (yes / edit)"
2. On yes, write the message to a temp file **outside the project** with
   `mktemp -t contact-nova-caelum.XXXXXX`, then build the link. The helper
   adds the "[Technical Cofounder] " prefix, which tells the founder where
   the message came from:

   `python3 "${CLAUDE_PLUGIN_ROOT}/bin/ask_issue.py" whatsapp-link <path>`

   - If it prints `NOT_SET`, say: "Messaging the founder directly is being
     set up. For now you can leave a note on GitHub," then offer Route 2.
   - If it prints `FAILED: <reason>`, say the WhatsApp link couldn't be
     built and offer Route 2.
   - If it prints `OPEN: <link>`, continue.
3. Open the link: `open "<link>"` on macOS, `start "" "<link>"` on Windows,
   `xdg-open "<link>"` on Linux. The link opens WhatsApp, or WhatsApp Web
   if the app isn't installed, with the message already typed.
4. Say: "WhatsApp is open with your message. Press send and the founder
   will reply to you there."
5. If the link won't open, print it and add: "Or message +<the digits
   between `wa.me/` and `?` in the link> on WhatsApp."
6. Delete the temp file.

Their WhatsApp chat is how the founder gets back to them, so there's no
contact detail to collect.

## Route 2: a public note on GitHub (no reply promised)

1. Say plainly that this becomes a **public** GitHub issue on
   `Nova-Caelum/technical-cofounder`. Leave out anything private.
2. Write the message to a temp file **outside the project** with
   `mktemp -t contact-nova-caelum.XXXXXX`.
3. Redact the file, which prints counts only:
   `python3 "${CLAUDE_PLUGIN_ROOT}/bin/ask_issue.py" redact <path>`
   Then show the whole message and ask: "Post this publicly? (yes / edit / no)"
4. On yes, post it:
   `python3 "${CLAUDE_PLUGIN_ROOT}/bin/ask_issue.py" post <path> --title "<one line>"`
   - If it prints `POSTED: <url>`, give them the link.
   - If it prints `OPEN: <link>`, give them the link, and say it opens a
     pre-filled issue that needs a free GitHub account.
5. Delete the temp file.

## Always

- Nothing is ever sent without their yes.
- Only offer this yourself once in a stretch, after something keeps failing.
- If they pick the public note but want a reply, say that the WhatsApp
  option is the one that gets a reply.

Source: Nova Caelum (Apache-2.0).
