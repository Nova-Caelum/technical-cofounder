---
name: get-api-keys
description: Use when the user asks how to get or add a Context7, Exa, or Browserbase key, why an MCP server in this plugin is failing to connect, or wants to know what each key unlocks.
---

# Get API Keys

First time with an API key? Use `technical-cofounder`'s `super-setup` skill instead: it walks you through a safe way to keep keys, each account and entering them. This page is the per-service reference.

`super-novacaelum` runs three hosted MCP servers — Context7, Exa, and Browserbase — on your own keys. None of the keys ship in this plugin; each is entered through Claude Code's own secure storage, never as a file in this repo.

## Context7 — documentation lookup (`find-docs` skill)

- **Adds:** current library, framework, SDK, and API documentation instead of stale training data.
- **Free tier:** works with no key at a lower rate limit. A key raises that limit.
- **Get a key:** context7.com/dashboard.
- **Check it works:** ask a library-specific question (`find-docs` fires automatically) and confirm the answer cites current docs rather than a training-knowledge caveat.

## Exa — web search (`web-research` skill)

- **Adds:** live web search and full-page reads for facts, news, and research a static knowledge base can't cover.
- **Free tier:** works with no key at a lower rate limit. A key raises that limit.
- **Get a key:** dashboard.exa.ai/api-keys.
- **Check it works:** ask a current-events or pricing question (`web-research` fires automatically) and confirm it returns cited, dated sources.

## Browserbase — cloud browser (`web-research` skill, escalation path)

- **Adds:** a real cloud browser for pages that need a click, a login, or an expandable section before their content is readable — Exa alone can't drive one.
- **Free tier:** a free plan exists (no credit card) with a small number of concurrent sessions and a monthly browser-time allowance; see browserbase.com/pricing for current limits.
- **Needs a key to run at all** — there's no anonymous mode, since a cloud browser session isn't free to host. Without one, the server is present but every connection attempt fails.
- **Get a key:** your Browserbase dashboard, after signup at browserbase.com.
- **Check it works:** ask something that needs an interactive page (`web-research` escalates to Browserbase automatically when Exa can't reach the content) and confirm a session starts instead of a connection error.

## How to enter a key

Inside Claude Code, opened in the project, run `/plugin configure super-novacaelum@technical-cofounder` (or open `/plugin`, pick super-novacaelum, choose configure) and paste each key into its hidden field. Every field is optional. The value goes to Claude Code's secure credential storage (on a Mac, the login Keychain), never this repo or plain settings.

Don't put a key on the install command line: the terminal keeps it in its history file. Never paste one into chat or a project file either.

Source: Nova Caelum (Apache-2.0).
