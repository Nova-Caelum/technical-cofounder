---
name: ask-nova-caelum
description: Use when the user says they're stuck, found a bug, have a feature request, want to share feedback, or want to ask Nova Caelum something directly, or offer it once yourself after something keeps failing.
---

# Ask Nova Caelum

A path back to the people who built this, from inside the session. It drafts
a message, shows you the **entire draft**, and posts it — as a **public**
GitHub issue on `Nova-Caelum/technical-cofounder` — only after an explicit
yes. Offer it once; never send it on your own.

The user may be frustrated. Plain words, one question at a time.

## When

- They say they're stuck, found a bug, have an idea, want to give feedback,
  or want to reach the makers.
- You already offered it once after something kept failing, and they haven't
  asked for it again — don't offer twice in the same stretch.

## Steps

1. Ask what kind it is, in one line: help, bug, idea, or feedback.
2. Ask what they were trying, what happened, and what they already tried.
   Draft it yourself from the conversation so far, and ask them to correct
   it.
3. Say plainly: this becomes a **public** GitHub issue. Leave out anything
   private — client names, code that isn't theirs to share, keys. Anything
   they'd rather not post can be trimmed out first.
4. Write the draft to a temp file **outside the project**, so it can never
   end up committed — `mktemp -t ask-nova-caelum.XXXXXX`. Then run, with the
   Python from setup as `<python>`:

   ```
   <python> "${CLAUDE_PLUGIN_ROOT}/bin/ask_issue.py" redact <path>
   ```

   It rewrites the file in place and prints only redaction counts — never
   the matched text. Show the **entire draft**, plus those counts.
5. Ask: **"Post this publicly? (yes / edit / no)"**
6. On yes, run:

   ```
   <python> "${CLAUDE_PLUGIN_ROOT}/bin/ask_issue.py" post <path> --title "<one-line title>"
   ```

   Titles get the `[ask] ` prefix automatically if it's missing.
   - If `gh auth status` succeeds, it posts via `gh issue create
     --body-file` (your redacted draft) and prints `POSTED: <url>` — give
     them the link.
   - Otherwise it prints `OPEN: <a prefilled issues/new? link>` — give them
     the link, and say it opens a pre-filled issue in their browser (a free
     GitHub account is needed). Mention that installing `gh` and running
     `gh auth login` makes it one step next time.

   On edit, go back to step 2 with their correction. On no, stop.
7. Delete that temp file — the path `mktemp` printed.

## Red flags

- Never paste a key, token or `.env` content into the draft, even planning
  to redact it after — leave it out instead.
- Never post without an explicit yes.
- Never post on the user's behalf to any repo other than
  `Nova-Caelum/technical-cofounder`.

Source: Nova Caelum (Apache-2.0).
