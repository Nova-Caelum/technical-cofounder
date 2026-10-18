# Try Technical Cofounder in Codex

**Draft for the planned `codex-rc.1` release; not a readiness signoff.** R1 supplies the harness and hook/context changes. R2–R5 still supply model routing, default judge isolation, full setup, and research. R6 must validate the final tag twice before this guide is handed to a friend. The tag is a planned release target, not a claim that it exists today.

The acceptance surface is **macOS, local Codex CLI**. Desktop is optional and needs separate evidence. Windows, marketplace packaging, Hyperspace standalone packaging, relocation/removal and optional super connectors are tracked in the parity phase.

## 1. Get one source and check prerequisites

Use a normal code folder outside a synced notes vault. You need Git, Bash, jq, system Python 3.11+, and Codex CLI. The native shell-result reader currently supports **Codex 0.162.0**; other versions retain breaker state with a diagnostic until verified. Sign in with `codex login` using your own account. Never paste credentials into chat.

The planned role mapping uses Terra, Sol and Astra. Use a Plus-or-higher account with access to those tiers. Tier fallback and its disclosure are an R2/R4 acceptance check; they are not yet implemented in R1.

After R6 publishes the readiness tag:

```sh
git --version
bash --version
jq --version
python3 --version
codex --version
mkdir -p "$HOME/NovaCaelum_code/tc-codex-friend"
cd "$HOME/NovaCaelum_code/tc-codex-friend"
git clone --branch codex-rc.1 https://github.com/Nova-Caelum/technical-cofounder.git tc-source
git init friend-project
```

Keep using this shell. Resolve any missing prerequisite using its official instructions. Do not use a project virtualenv for the installer. The installer fetches the exact engine pin into `~/.cache/tc-codex`; a second clone is unnecessary. `--engine-source` remains available for an existing clean checkout at the exact pin.

## 2. Install, provision and check the engine

```sh
python3 tc-source/scripts/install_codex.py --project "$PWD/friend-project"
cd friend-project
python3 -I .codex/technical-cofounder/adapter.py provision --project "$PWD" --judge codex
.hyperspace/env/bin/hyperspace doctor --dir "$PWD"
```

The target release enables the Codex judge by default. This draft selects it explicitly because the R1 adapter still defaults to `none`; R3 changes the default and verifies isolation before release. Provisioning downloads Python packages into `.hyperspace/env`. The judge uses your signed-in Codex account for model-based verification. A small closure ordinarily needs one small judge request, but multiple criteria, retries or review stages can use more; this is not a fixed dollar estimate. To disable it, rerun provisioning with `--judge none`. File/command criteria remain available; semantic judge verification does not.

Expected: installation reports its managed-file count, provisioning records environment provenance, and doctor reports no failures. Generated files include skills in `.agents/skills`, four roles in `.codex/agents`, persona plus all five workspace rules in `AGENTS.md`, and project MCP/hook configuration. The managed project config raises the instruction budget to 131072 bytes. Trust the project before testing those instructions.

The greeting acceptance check uses the engine's registered `tests` check, which
runs pytest even when the tests use standard-library unittest. Prepare a project
test environment (separate from the engine runtime) in this shell before opening Codex:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r ../tc-source/docs/codex-rehearsal-requirements.txt
```

## 3. Review trust in the CLI

```sh
codex
```

Review `AGENTS.md`, `.codex/config.toml` and `.codex/hooks.json`. Accept project trust after that review. In `/hooks`, review and trust the six generated command definitions, then start a fresh session. Project trust and hook-definition trust are separate. The installer grants neither. Expect to review each fresh project; cross-project reuse is recorded by the rehearsal rather than assumed. Identical reinstall preserves definitions. Do not bypass hook trust.

Check the skill picker for `tc-setup`, `assumption-check` and `hyperspace-setup`. Both **caelum-dev-team** and **hyperspace** must connect. Ask for `worklog_recent` and Hyperspace `list_projects`; a configured server list alone is not proof. Retain any failure and rerun doctor. Do not bypass a provenance refusal.

## 4. Ask the team to do one small, verifiable task

Paste the contents of [`codex-friend-task.txt`](codex-friend-task.txt) into this fresh session. The rehearsal reads that same file, so the running acceptance task and this guide stay in sync:

> Run $tc-setup, preserving my existing profile. Then build a tiny Python greeting function and a meaningful unittest in this disposable project. Use a fresh task directory and unique graph external ID for each attempt; never reuse completed files from an earlier attempt. Record the project graph row before creating implementation or test files. Include a file_state criterion for the new greeting function and a command_check with check_id=tests targeting the fresh task directory. The registered tests check runs pytest; ensure the project .venv has pytest and run the unittest through that same pytest runner. Delegate implementation to engineer and an independent review to devops-lead using the installed roles. Show me the verification result, append a short local worklog entry and read back that entry. Do not mark the row done if verification fails. Tell me if a role, skill, hook or MCP tool is unavailable. Do not change hook trust or bypass a guard.

Expected at readiness: setup guide/progress are visible; the existing profile survives; engineer and devops-lead run in separate threads on their configured tiers; the test passes; the graph verifier closes the row only after its criteria pass; the worklog entry reads back. A self-review is not independent audit evidence. Open the graph with `.hyperspace/env/bin/hyperspace serve --open`. R1's staged harness keeps `judge=none` and records later-row gaps; that staged run does not satisfy final readiness.

## 5. Send a compact result

Record OS, CLI version, TC commit (`git -C ../tc-source rev-parse HEAD`), install/provision/doctor results, skills, actual role/model execution, MCP calls, hook trust and execution, test result, graph state and worklog readback. Include exact errors and the step where they occurred. Remove secrets before sharing.

Keep the disposable project until review. Reinstall with the same source/project paths; the installer refuses edited managed files. Moving a project or removing its system Python requires regenerating installation configuration. Automatic update and removal are deferred to parity.

## Known limits

Native Stop continuation and its retry flag are awaiting the rehearsal's temporary
20-word threshold probe. The production threshold remains 700 words, above the
binding response budget (at most 650); deterministic block/guard tests pass, but
ordinary native Stop dispatch does not prove continuation. Per CTO review this
verbosity backstop is a documented limitation rather than a readiness blocker.
