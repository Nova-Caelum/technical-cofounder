# Codex rehearsal evidence

R1 is a staged collector, not an automatic row close or readiness signoff. Run deterministic preparation from Codex; live turns must run from the user's Terminal or a Claude Code shell under plan A4. No trust is granted or bypassed.

```sh
python3 scripts/rehearse_codex.py --tc-ref <commit> --root ~/NovaCaelum_code/tc-rehearsal/r1-<commit>
```

This clones exact TC/HSE refs, installs twice into two disposable git projects, checks managed hashes, provisions with `judge=none`, runs doctor, exercises installed guards, measures SessionStart/freshness output and verifies a local MCP worklog round trip. It refuses the synced vault, nonempty unowned roots, changed refs in an existing root, and edited managed files. `--tc-source` and `--engine-source` can name local clean repositories. Keep dependencies outside the vault.

Review project trust and the six definitions in the primary project's CLI `/hooks` before live collection. Do not pre-trust the secondary copy: the run records whether identical definitions carry trust across projects. If they do not, the documented fallback is one review per fresh project. Then, from the external runner:

```sh
python3 scripts/rehearse_codex.py --tc-ref <commit> --root ~/NovaCaelum_code/tc-rehearsal/r1-<commit> --runner user-terminal --turns
```

`results.json` links raw protocol, trace, counter observations, instruction samples, compaction, Stop retry, apply_patch, and the exact friend-task prompt hash. It checks managed files and the global configuration hash before/after. Native turns use normal workspace-write sandboxing with no approvals; interactive server requests are refused. Hooks and trust remain unchanged.

`deterministic_pass_live_pending` means only deterministic checks passed. `requires_hook_trust` stops before model turns. `collected_needs_review` means collection finished and a reviewer must inspect each behavior against its raw evidence. A model declining the oversized Stop reply or failing the friend task leaves that requirement unproven. The collector never closes a work item; verifier closure is a separate requirement. Unsupported probe rows are rejected until their checks are implemented.

Trace metadata is opt-in via `TC_HOOK_TRACE`: event and call IDs, handler exit codes, native status source, Stop word counts/retry flag, and drive-context injection. It omits command text, prompt and response bodies. Raw app-server transcripts can contain task and workspace content; keep evidence local unless its contents have been reviewed for sharing.
