---
name: secrets-setup
description: Use when a key or secret comes up, or code is about to need one. The user says "API key", "secret", ".env", "where do I put my key" or "I leaked a key", or wants Stripe, OpenAI or a database in their own app.
---

# Secrets Setup

A secret lets a program act as you: an API key (a long password a program uses to reach a service), a token, a database password. Keep secrets out of chats, code and git history (every saved version of the project). Ask one question at a time; explain each term once.

**The rule:** never ask for, read or repeat a secret's value. The user types it into their password manager, editor or host settings. A key pasted here counts as leaked: step 3.

Ask first: "Do you use a secrets manager, or want one?" A secrets manager hands an app its keys when it runs, so they sit in no file. Yes: step 2A. No, or no extra tools: step 2B. Everyone does step 1 and ends at step 3.

## 1. Personal practice

If unknown, ask: "Where do you keep passwords today?" No fortress, a few habits:

- **One home for keys:** a password manager (an app that stores passwords safely). Theirs, their device's (Apple Passwords, Google Password Manager) or free Bitwarden.
- **One entry per service,** named after it.
- **Two places only:** the password manager, and wherever the program reads the key.
- **Never paste a key into a chat (this one included),** a doc, an email or a screenshot, or type it on the command line (shell history keeps it).
- **Turn on any spend limit** the service offers.

## 2. Project secrets

For their own app, on both paths:

- **Never put a secret in client-side code** (code that runs in the browser or a phone app): every visitor gets a copy, and names starting `NEXT_PUBLIC_` or `VITE_` are built into it. Keep secrets on the server. Publishable keys (Stripe's, Supabase's anon key) are meant to be public.
- **In production** (the live app), use the host's secret or environment settings (Vercel, Netlify and others have one), never a committed file.

### 2A. With a secrets manager

Set up theirs. No preference? Suggest Doppler or Infisical: free tier, browser login, one run command. On a Mac:

- **Bitwarden Secrets Manager** (free: 2 users, 3 projects): download `bws` from github.com/bitwarden/sdk-sm/releases. It needs a machine-account access token in an environment variable (see its docs). Run: `bws run -- 'npm run dev'`.
- **1Password** (no free plan; if they already pay): `brew install 1password-cli`, then turn on Settings › Developer › Integrate with 1Password CLI. Run: `op run --env-file=.env -- npm run dev`, with `.env` holding `op://` references.
- **Doppler** (free up to 3 users): `brew install gnupg`, `brew install dopplerhq/cli/doppler`, `doppler login`, `doppler setup`. Run: `doppler run -- npm run dev`.
- **Infisical** (free up to 5 identities): `brew install infisical/get-cli/infisical`, `infisical login`, `infisical init`. Run: `infisical run -- npm run dev`.

Values go in through the tool's app or website, never here.

### 2B. Without one: the plain protocol

The password manager is the source of truth. `.env` (a file of `NAME=value` lines the app reads) is a local copy.

1. **Ignore first.** Before any key is written, `.gitignore` (the list of files git never saves) must list `.env` and `.env.*`, then `!.env.example`. Commit it.
2. **Create `.env` with names only,** like `OPENAI_API_KEY=`. If it exists, add missing names; never overwrite it. The user pastes the values in their own editor; after that, don't open or print `.env`.
3. **Commit `.env.example`** with the same names and no values, so the next person or AI session knows them.
4. **Read from the environment:** `process.env.OPENAI_API_KEY` in JavaScript, `os.environ["OPENAI_API_KEY"]` in Python. The framework or `dotenv` loads `.env`.

## 3. Check, and the leak response

From the project root; searches print file and line only, never the value.

```
git check-ignore .env
git grep -nIiE --untracked '(^|[^A-Za-z0-9])(sk|rk)[-_][A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9]{36}|PRIVATE.KEY-----|(key|secret|token|password)[A-Za-z_]*[^A-Za-z0-9]{1,4}[A-Za-z0-9/+_]{24,}' | cut -d: -f1,2
git rev-list --all | xargs -r git grep -nIiE '(^|[^A-Za-z0-9])(sk|rk)[-_][A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9]{36}|PRIVATE.KEY-----|(key|secret|token|password)[A-Za-z_]*[^A-Za-z0-9]{1,4}[A-Za-z0-9/+_]{24,}' | cut -d: -f2,3 | sort -u
```

No output from the first means `.env` isn't ignored: see 2B, item 1. The second searches current files, the third every saved version; some hits are false alarms. If GitHub blocks a push for a key, don't bypass it; see below.

If a real key ever reached a commit, a chat, a screenshot or a browser:

1. **Revoke it first** in the service's dashboard (revoke, delete or roll). Deleting the line does not remove it: earlier commits in the history still hold it, and bots scan public repositories within minutes.
2. **Create a new key**, stored as in step 2A or 2B.
3. **Then clean up:** read it from the environment instead, and commit. Rewriting history (`git filter-repo`) is optional once the old key is dead; it needs a force push, so ask first.

## Red flags

| What happens | Do |
|---|---|
| A key is pasted into this chat | Don't use or repeat it. It's leaked: step 3. |
| A key is headed for a file git saves (code, config, an un-ignored `.env`, `.env.example`) | Stop. Ignore `.env` first; the example gets names only. |
| A key is headed for the command line | Don't. Shell history keeps it. |
| A screenshot or shared screen | Check no key shows. If one did, it's leaked. |
| A secret is headed for browser code or a `NEXT_PUBLIC_`/`VITE_` name | Stop. Server only. |
| "I deleted the line, so it's gone" | It isn't. Revoke first. |

Source: Nova Caelum (Apache-2.0).
