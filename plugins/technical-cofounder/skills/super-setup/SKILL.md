---
name: super-setup
description: Use when someone wants to set up super (super-novacaelum) or get an API key, especially a person who has never used an API before. They say "set up super", "install super", "add my API key", "I've never used an API", or "where do I put my key". Walks them through a simple safe way to keep keys, creating each account, the project-scope install and entering each key through Claude Code's hidden prompt.
---

# Super Setup

Get super-novacaelum working for someone who may never have used an API. Ask one question at a time, in plain words; explain each term the first time.

Accounts and keys are between the user and each service. Nova Caelum never sees them, and neither should this chat.

## 1. Gauge

Ask, one at a time:

1. "Have you used an API key before?" If not, explain: an API is a way for one program to ask another for something, and an API key is a long password that identifies you to the service and counts your usage.
2. "Where do you keep passwords today?"

Fit the rest to their answers.

## 2. A simple, safe practice

If they don't have one yet, run `secrets-setup` step 1: a password manager and a few habits. These keys are low-risk (the worst case is someone burning your quota), so keep it light. Then come back here.

## 3. Choose services

All optional. Suggest starting with only what they need:

- **Context7:** current documentation for code libraries. No key needed; a key raises the limit.
- **Exa:** web search and page reading. No key needed; a key raises the limit.
- **Browserbase:** a cloud browser for pages that need a click or a login. Needs a key to work at all.

## 4. Accounts and keys

For each chosen service, one at a time: sign up, open the key page, create a key, and save it straight into its password-manager entry. Tell them not to show you the key.

| Service | Sign up, then the key page | Free tier (checked 2026-09-25) |
|---|---|---|
| Context7 | context7.com/dashboard, then Create API Key. It shows the key once. | Free plan, 1,000 calls a month |
| Exa | dashboard.exa.ai, then API Keys (dashboard.exa.ai/api-keys) | $20 free credits, then $10 free a month. Leave auto recharge off. |
| Browserbase | browserbase.com/sign-up, then browserbase.com/settings | Free plan, 1 browser hour |

## 5. Install

In a terminal (the window where you type commands), from the project root (its top folder), run:

```
claude plugin install super-novacaelum@nova-caelum --scope project
```

The `nova-caelum` catalog is already on this computer: setup added it. If the command says it does not know that catalog, add it first with `claude plugin marketplace add https://github.com/Nova-Caelum/plugins.git`, then run the install again.

`--scope project` turns super on for this project only. A note that options aren't set yet is expected.

## 6. Enter keys

In Claude Code, opened in the project, run `/plugin configure super-novacaelum@nova-caelum`, or open `/plugin`, pick super-novacaelum and choose configure. It asks for each key in a hidden field (Claude Code's docs say these fields are masked). Copy the key from the password manager, paste it into that prompt, press Enter. Never paste a key into this chat instead. Skip services they didn't choose.

Where it goes: on a Mac, the login Keychain (the Mac's built-in password store). Tested on macOS, through the store this prompt uses: the key landed there and in no settings or project file. Without a supported keychain, Claude Code's docs say it uses a credentials file in its own settings folder, outside the project.

If the new tools don't appear, run `/reload-plugins` or restart Claude Code.

## 7. Check it works

From the project root, run `claude mcp list`. Each service is a server (the connection that hands Claude the tool), like `plugin:super-novacaelum:exa`, and should read Connected. Browserbase reads "Failed to connect" until its key is in.

Then one tiny call each:

- Context7: "Look up the current docs for <a library they use>."
- Exa: "Search the web for <something recent>, with links."
- Browserbase: "Open example.com in the cloud browser; what's the title?"

If one fails, re-enter that key as in step 6.

## 8. Close

Three lines:

- **Installed:** super-novacaelum here, with their chosen services.
- **Keys live in:** their password manager and Claude Code's protected store (the Keychain on a Mac). Nowhere else.
- **If one leaks:** revoke it in that service's dashboard, create a new one, and enter it with `/plugin configure`.

## Red flags

| What happens | What to do |
|---|---|
| The user pastes a key into this chat | Don't use or repeat it. It now counts as leaked: revoke it, create a new one and enter it as in step 6. |
| A key is about to go into a project file (`.env`, `.mcp.json`, settings) | Stop. Plugin keys go in only through the configure prompt; keys for the user's own app go through `secrets-setup`. |
| A key is about to go on the command line (the install's `--config` flag) | Don't. The terminal saves every command in its history file, key included. |
| The user wants to share a screenshot or their screen | Check first that no key is visible. If one was, treat it as leaked (row 1). |

Source: Nova Caelum (Apache-2.0).
