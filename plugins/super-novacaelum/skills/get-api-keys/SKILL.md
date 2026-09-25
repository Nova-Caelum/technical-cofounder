---
name: get-api-keys
description: Use when the user asks how to get or add a Context7, Exa, or Browserbase key, why an MCP server in this plugin is failing to connect, or wants to know what each key unlocks.
---

# Get API Keys

`super-novacaelum` runs three hosted MCP servers — Context7, Exa, and Browserbase — on your own keys. None of the keys ship in this plugin; each is entered through Claude Code's own secure storage, never as a file in this repo. Sequential-thinking, the plugin's fourth server, needs no key at all — it runs as a local process.

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

Either path stores the value in Claude Code's secure credential storage — never in this repo, never in plain settings:

- **At install:** `claude plugin install super-novacaelum@technical-cofounder --scope project --config context7_api_key=YOUR_KEY --config exa_api_key=YOUR_KEY --config browserbase_api_key=YOUR_KEY`. Omit any `--config` flag you don't have a key for yet — each field is optional.
- **After install:** run `/plugin configure super-novacaelum` inside Claude Code, or enable the plugin fresh, which prompts for each field.

Source: Nova Caelum (Apache-2.0).
