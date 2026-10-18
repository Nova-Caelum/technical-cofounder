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

`results.json` links raw protocol, trace, counter observations, instruction samples from each byte-third of the actual generated AGENTS.md (including the tail beyond 32 KiB), compaction, Stop dispatch (retry remains unproven), apply_patch, and the exact friend-task prompt hash. It checks managed files and the global configuration hash before/after. Native turns use workspace-write sandboxing with network access off. MCP approval requests go to Codex automatic review, which may approve or deny each action and consumes additional model usage. Sandbox escapes, rule approvals and permission grants remain disabled; the collector refuses any interactive server request it receives. It records the effective policy and stops if the host broadens the requested boundary. Hooks and trust remain unchanged.

`deterministic_pass_live_pending` means only deterministic checks passed. `requires_hook_trust` stops before model turns. `collected_needs_review` means collection finished and a reviewer must inspect each behavior against its raw evidence. Ordinary Stop dispatch does not prove retry behavior; a failed friend task leaves its acceptance requirements unmet. The collector never closes a work item; verifier closure is a separate requirement. Unsupported probe rows are rejected until their checks are implemented.

Trace metadata is opt-in via `TC_HOOK_TRACE`: event and call IDs, handler exit codes, native status source, Stop word counts/retry flag, and drive-context injection. It omits command text, prompt and response bodies. Raw app-server transcripts can contain task and workspace content; keep evidence local unless its contents have been reviewed for sharing.

## Repeating a collection

Each collection gets a fresh drive-probe path, greeting directory and graph ID.
Existing results stay intact; the collector refuses a colliding or escaped path.
The shared friend task files its graph criteria before implementation. Its task
source comes from the collector checkout, is hashed and saved with the effective
prompt; it does not silently reuse the task from an older installed source.

The registered engine `tests` check uses pytest. Deterministic preparation installs
`codex-rehearsal-requirements.txt` into a collector-owned project `.venv`, separate
from `.hyperspace/env`. Native collection resolves the interpreter through the
installed verifier and checks pytest before starting Codex. For an already prepared
installation, add these dependencies without reinstalling or retrusting hooks:

```sh
python3 scripts/rehearse_codex.py --tc-ref <installed-commit> --root <existing-root> --prepare-checks
```

The native Stop continuation/retry requirement is still open. The earlier prompt
requested 710 words despite a binding response budget no higher than 650. A
compliant refusal cannot exercise the greater-than-700-word defensive branch.
The collector no longer spends a model turn asking for that violation. Installed
synthetic tests exercise the block decision and `stop_hook_active=true`; ordinary native
Stop dispatch is recorded, but neither is labeled native continuation proof.
A separately reviewed test design or explicit plan amendment is required to close
this requirement; hook policy and trust are unchanged.
