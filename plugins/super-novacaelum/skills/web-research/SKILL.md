---
name: web-research
description: Use for current facts, news, pricing, releases, or any claim that needs open-web verification — not library or API documentation (see find-docs) and not synthesis of material already in the conversation.
---

# Web Research

Research discipline for the `exa` and `browserbase` MCP servers this plugin configures. Exa is the default route for search and page reads; Browserbase is the escalation for pages Exa's crawl cannot reach because they require a click, a login wall, or an expandable section.

Not for: library or SDK documentation lookups — use `find-docs` instead, which routes to Context7. Not for summarizing content the user already supplied in the conversation, unless it needs external verification.

## Route

1. **Search with Exa's search tool.** Give it a narrow, well-formed query — describe the page you want, not a keyword list.
2. **Read the search results first.** Stop once the returned snippets support the answer.
3. **Fetch full page content with Exa's fetch tool when snippets don't suffice.** Give it the URL(s) you found; it returns the page as clean markdown.
4. **Escalate to Browserbase only when a known URL needs interaction** Exa's fetch can't provide — a consent wall, an expandable section, a client-rendered page, or a login-gated view. Start a session, navigate to the URL, observe or act as needed, extract the content, then end the session.
5. **Limit Browserbase to three attempts per blocked URL** (one attempt = one full start-to-end session). If the content is still unreachable, say so and use another source or ask the user for access — never loop.

Exa search-then-fetch is the default full path. Browserbase is the escalation for one blocking case, not an alternate default.

## Query and source discipline

- Quote exact multi-word phrases and use `site:` for a known primary source.
- Start narrow, check results, then refine once if needed — don't repeat the same broad query.
- Prefer primary sources: official docs, vendor domains, release notes, source repos. Cross-check consequential claims when feasible.
- Treat unverified blogs and forum posts as leads, not sole evidence.

## Evidence and reporting

- Cite each web-derived factual claim with its source link.
- Note publication or update dates when recency matters.
- Say plainly when sources disagree, access was incomplete, or a claim is your own inference.
- Never claim a page was read if extraction failed or only a search snippet was available.

## Rate limits and keys

Both servers work without a key at lower limits (Browserbase needs one to run at all — a cloud browser session isn't free to host anonymously). See the `get-api-keys` skill for where to get each key and how to add it.

## Tool names

Confirmed against Exa's and Browserbase's own hosted-MCP documentation during this plugin's build (2026-09-25): Exa exposes a search tool and a fetch tool by default; Browserbase exposes session start, navigate, act, observe, extract, and session end. Read your session's live tool list under the `exa` and `browserbase` servers if these differ — a vendor can rename or add tools after this file is written.

Source: Nova Caelum (Apache-2.0). Adapted from the Nova Caelum internal `web-search` skill; this version targets the hosted Exa and Browserbase MCP servers this plugin configures and drops the third search-engine fallback that skill used, which this plugin doesn't ship.
