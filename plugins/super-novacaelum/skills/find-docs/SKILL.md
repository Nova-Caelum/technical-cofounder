---
name: find-docs
description: Use when a question is about a specific library, framework, SDK, API, or CLI tool — syntax, configuration, version migration, or setup — even a well-known one, since training data can be stale. Prefer this over general web search for library and API documentation.
---

# Find Docs

Fetch current documentation through the `context7` MCP server instead of answering library and API questions from memory. Training data drifts behind releases; Context7 resolves a library name to a maintained documentation index and returns the current, relevant excerpt.

Not for: refactoring, writing scripts from scratch, debugging business logic unrelated to a library's own API, or general programming concepts that no library owns.

## Workflow

Two calls, in order:

1. **Resolve the library.** Call the resolve tool with the library's proper name (`"Next.js"`, not `"nextjs"`; `"Three.js"`, not `"threejs"`) and the question as the query — the query ranks results, so a specific one returns a better match than a bare name. Pick the best match by name match, description relevance, snippet coverage, and source reputation. If nothing looks right, retry with an alternate name or a rephrased query before giving up.
2. **Fetch the docs.** Call the docs tool with the resolved library ID and the full question as the query. A vague one-word query returns generic results — use the user's actual question.

Do at most three calls total across both steps per question. If nothing useful turns up after three, say so and answer from training knowledge with an explicit note that it may be outdated — never silently fall back.

## Anonymous use and rate limits

This server works without a key at lower limits. If `find-docs` is hitting quota errors, see the `get-api-keys` skill for where to get a free Context7 key and how to add it — no code change is needed, only the plugin configuration.

## Tool names

The two tools this skill drives were confirmed live against the Context7 MCP connection during this plugin's build (2026-09-25): a resolve tool that returns candidate library IDs, and a docs tool that takes a resolved ID plus a query and returns documentation snippets. Read the tool list your session actually exposes under the `context7` server if these differ — MCP tool names are supplied by the live connection, not fixed by this file.

Source: Nova Caelum (Apache-2.0). Adapted from the Nova Caelum internal `find-docs` skill, which wraps the Context7 CLI; this version targets the hosted Context7 MCP server this plugin configures instead of a CLI.
