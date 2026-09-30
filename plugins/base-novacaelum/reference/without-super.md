# Working without super-novacaelum

super-novacaelum adds three services, each on the user's own account. When the session preload's tech primer says super isn't present, use the base fallback in the same row. Say which fallback you used, and never imply a super service ran.

| Super service | What it gives | Base fallback |
|---|---|---|
| Context7 (`find-docs`) | Current documentation for a library, framework or tool | Fetch the official docs page with Claude Code's built-in web fetch (WebFetch), and cite its link. |
| Exa (`web-research`) | Web research with sources | Use Claude Code's built-in web search (WebSearch), and cite each link. |
| Browserbase | A cloud browser for pages that need clicks, a login or JavaScript | No base equivalent: ask the user to open the page and tell you what it shows. |

To add super later, say "continue setup" (its step is `super`) or run `/base-novacaelum:quick-start`.

Source: Nova Caelum (Apache-2.0).
