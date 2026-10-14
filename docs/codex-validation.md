# Codex preview: implementation and verification

Verified on 2026-10-14. This is a local macOS/Linux preview generated from shared TC sources and Hyperspace Engine revision `45472d4260b65ecec1f194bdd044fba9880f42e4`. [Friend test](codex-friend-test.md).

## Boundary

`scripts/install_codex.py` generates a project installation. `codex/adapter.py` translates host events and launches the existing runtime. Shared personas, hooks, normalization rules, Python MCP server and environment-provenance gate remain unchanged. The installed runtime has a manifest with source revisions and hashes; updates regenerate it from source. Native role instructions inherit the user's model.

The generated AGENTS entry point explicitly requires the separate shared workspace-rules document. This avoids exhausting Codex's default 32 KiB project document budget. Installation refuses an oversized combined AGENTS file; additional ancestor instruction files can also consume the host's total budget and should be reviewed in existing projects.

Setup is explicit. Installation neither provisions dependencies nor grants trust. Provisioning with `judge=none` enables deterministic verification; choosing a live Codex judge requires separate authentication and user intent. The project interpreter is executed only after the unchanged shared provenance gate approves it.

Codex has no PostToolUseFailure event. The adapter classifies explicit shell exit codes and MCP `isError` fields, then calls the shared breaker. Unknown formats retain counters and emit a diagnostic. Native failures without a PostToolUse event remain outside this boundary. A transcript path distinguishes subagents sharing a session ID; without it or an explicit agent ID only session isolation is available. Shared warn/block/reset behavior is preserved for supported results.

## Executed checks

- Full TC unittest discovery: 880 tests, 14 platform/optional integration skips, no failures.
- Codex tests: 21 passed. These cover preservation/idempotence, native role TOML, shared-source parity, untracked-file exclusion, collision/symlink/edited-file refusal, instruction budget, required dependencies, circuit breaker warn/block/reset, ambiguous results, thread isolation, concision retry, patch/drive-map context and provenance refusal before a planted interpreter executes.
- Real pinned-engine provisioning in a disposable project created the isolated environment, graph database and provenance record with judge=none.
- Codex CLI 0.162.0 app-server, with a disposable CODEX_HOME and an explicitly trusted disposable project, discovered all 20 repository skills and six project hook commands. Hook definitions remained **untrusted**, as expected; this did not certify host-triggered hook execution.
- Native MCP startup connected `caelum-dev-team` (3 tools) and `hyperspace` (21 tools). Local worklog append/readback succeeded. The graph filed a typed file criterion, refused completion while the artifact was absent, then verified and read back `done` after the artifact was created. Both completion attempts reported zero model calls.
- Startup no longer reported AGENTS truncation after the companion-document fix.

Run the deterministic regression suite from this checkout:

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_codex -v
```

The native app-server check used `initialize`, `skills/list`, `hooks/list`, `thread/start`, `mcpServerStatus/list` and `mcpServer/tool/call`. No model turn or account credentials were supplied. The isolated, unauthenticated home emitted background login/warmup diagnostics; they did not prevent local discovery or MCP calls. No changes were made to the user's Codex trust configuration.

## Acceptance still requiring a friend

Live model behavior, custom role selection/delegation, the exact host hook approval/execution path and the optional paid Codex judge remain for the five-step friend test. No Windows, hosted cloud, optional super-service or public-directory compatibility claim is made. The original Claude install CI continues to run separately.

## Host contracts checked

- [OpenAI portable plugins](https://developers.openai.com/plugins/build/plugins)
- [Codex custom roles](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Codex skills](https://learn.chatgpt.com/docs/build-skills)
- [Codex hooks and trust](https://learn.chatgpt.com/docs/hooks)
- [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp)
