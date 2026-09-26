---
name: engineering-code-review
description: Use when reviewing or auditing code (a diff, PR, file or repo) for security, correctness, performance, maintainability or design fit, or when asked "review this", "is this secure?", "what's wrong with this?" or "check this before I merge". Findings, not fixes.
---

# Engineering Code Review

A systematic audit that ends in a prioritized findings report someone else can act on without a briefing. The reviewer finds, and the builder fixes.

## 1. Pick the review type

| Type | Focus | When |
|---|---|---|
| Security | Vulnerabilities, auth, data exposure | Before a release, a new integration or an auth change |
| Performance | Latency, scale, resource use, cost | Growth, a slowdown, an infrastructure choice |
| Design fit | Patterns, boundaries, debt | A new component or a large refactor |
| General | All five categories | PR reviews and general audits |

## 2. Read before you judge

- Read the diff and the code around it.
- Find the project's conventions: existing patterns, recorded decisions (ADRs), lint config and the README.
- Run the tests and the build if they exist. A review that ran nothing must say so.

Observed failure: a change was called done and pushed without anyone running the build. The build was broken, and the host kept serving the old version, so the site looked fine.

## 3. Work the five categories

Adapt the specifics to the stack in front of you (framework, database, host). The categories stay the same.

### Security
- **Injection.** Queries are parameterized and never built by concatenating user input. User input never reaches a shell command or a file path without validation.
- **Secrets.** None in source, committed config, logs, error messages or client-side code. They load from the environment or a secret store.
- **Authorization.** Checked on the server, on every route. Hiding a button in the UI is not access control.
- **Token comparison.** Secrets and tokens are compared in constant time.
- **Failure mode.** Errors fail closed. Nothing swallows an exception and carries on as if the request were authorized.
- **Dependencies.** Each new one is justified, pinned and from a trusted source.
- **Web code.** Sweep it against the OWASP Top 10.

### Correctness
- The logic matches the stated intent. Read the ticket or spec, not only the code.
- Edge cases are handled: empty, null, zero, negative, very large, unicode, concurrent.
- Errors surface loudly. Async failures are handled, and nothing hides in an empty `catch`.
- Tests cover the critical path, and at least one exercises it end to end.

### Performance
- Work that grows with the data: N+1 queries, quadratic loops over growing sets, unbounded queries, missing indexes.
- Redundant calls, missing caching on hot reads, oversized payloads and resource leaks.

### Maintainability
- Each function does one thing, and names explain themselves.
- No magic numbers. Comments say why, not what.
- No dead code or commented-out blocks.
- A new contributor could follow it without a walkthrough.

### Design fit
- It's consistent with existing patterns and recorded decisions, and module boundaries are respected.
- It introduces no new pattern that fights an existing one.
- Any debt it introduces is named and intentional. Whether surplus structure earns its place is a question for `overbloat-review`.

## 4. Write the report

Save it where the project keeps reviews, or as `reviews/YYYY-MM-DD-<subject>.md`, and summarize it in chat.

```markdown
# Code review: <subject>

**Date:** · **Type:** · **Scope:** <files, PR or commit range>
**Ran:** <commands and their results, or "nothing was run">

## Summary
<Two or three sentences: the overall verdict and the most important finding.>

## Findings
### [CRITICAL] <Category>: <short title>
**Where:** `path/to/file.ext:47`
**Problem:** <what is wrong and why it matters>
**Impact:** <what breaks or degrades if it ships>
**Fix:** <the specific change: where, and how>

### [MAJOR] …
### [MINOR] …
### [INFO] …

## Action list
1. CRITICAL: fix before deploy
2. MAJOR: fix before merge
3. MINOR: fix in the next pass
4. INFO: no action needed

## Handoff
<What the builder needs to do, by finding.>
```

## Severity

| Level | Meaning | Action |
|---|---|---|
| CRITICAL | A security breach, data loss or complete failure | Blocks deploy |
| MAJOR | A significant security or correctness problem | Fix before merge |
| MINOR | A quality improvement that doesn't block | Next pass |
| INFO | Good practice or context | None |

## Writing findings

- Give the exact file and line, every time.
- Explain why it's a problem, not only that it is one.
- Give a specific fix. Never write "add error handling" without saying where and how.
- Point to existing patterns in the codebase when you suggest an approach.
- Keep what blocks separate from what's nice to have.
- Write about the code, never about the person.
- Claim only what you checked. "I ran the tests" and "I didn't run anything" are both fine; implying one when the other happened is not.

Source: Nova Caelum (Apache-2.0).
