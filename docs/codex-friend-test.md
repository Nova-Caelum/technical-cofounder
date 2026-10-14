# Try Technical Cofounder in Codex

This preview installs the core team in one **local macOS or Linux project**. Use a disposable project for this first test. Windows, hosted cloud tasks, marketplace distribution and optional super connectors are outside this preview. The native integration check used Codex CLI **0.162.0**; your friend test establishes actual conversational behavior on your machine.

## 1. Get the two sources and check prerequisites

Use a normal code folder outside a synced notes vault. You need Git, Bash, jq, system Python 3.11+ and a local Codex installation with hooks and custom roles. Sign in to Codex using your own account. Do not paste credentials into chat.

```sh
git --version
bash --version
jq --version
python3 --version
codex --version
mkdir -p "$HOME/Code/tc-codex-preview"
cd "$HOME/Code/tc-codex-preview"
git clone --branch codex/tc-codex-compat https://github.com/Nova-Caelum/technical-cofounder.git tc-source
git clone https://github.com/Nova-Caelum/hyperspace-engine.git engine-source
git -C engine-source checkout --detach 45472d4260b65ecec1f194bdd044fba9880f42e4
mkdir friend-project
```

Keep using the same shell for the commands below. If a prerequisite is missing, install it using its official instructions before continuing. Do not use a Python virtualenv for the installer. The engine revision is intentionally pinned; do not substitute its latest main.

## 2. Generate the project installation, then provision the engine

```sh
python3 tc-source/scripts/install_codex.py \
  --project "$PWD/friend-project" --engine-source "$PWD/engine-source"
cd friend-project
python3 -I .codex/technical-cofounder/adapter.py provision \
  --project "$PWD" --judge none
.hyperspace/env/bin/hyperspace doctor
```

Expected: the installer reports its managed-file count; provisioning creates `.hyperspace/env`, initializes the graph, records environment provenance and writes the launcher. It downloads Python packages into this project. No model call is made with `judge=none`; file/command criteria can verify, but semantic/model judging is unavailable. A doctor result that reports the judge as `none` is consistent with this choice. Investigate any other failed check.

Installation generates 20 skills in `.agents/skills`, four roles in `.codex/agents`, the TC persona in `AGENTS.md`, and project hooks/MCP configuration. Shared policies and runtime sources are snapshotted with source revisions in `.codex/technical-cofounder-install.json`. It preserves pre-existing user content and refuses collisions or edited managed files. The installer does not grant project or hook trust.

## 3. Open a fresh local Codex session and review trust

Open `friend-project` in Codex Desktop as a **local** project, or run `codex` from this directory. Review the generated `AGENTS.md`, `.codex/config.toml` and `.codex/hooks.json`; trust this project only after that review. In `/hooks`, review and enable the six generated command definitions. Project trust and hook-definition trust are separate. Start a fresh session after accepting them.

Check the skill picker for `tc-setup`, `assumption-check`, `hyperspace-setup` and the other team skills. Check MCP status for **caelum-dev-team** and **hyperspace**; both must connect. `codex mcp list` shows their configuration but is not itself proof of connectivity. Ask for a `worklog_recent` call and a Hyperspace `list_projects` call. If either fails, run the doctor from step 2 and retain the diagnostic. Do not bypass an environment-provenance refusal.

## 4. Ask the team to do one small, verifiable task

Paste this into the fresh session:

> Run $tc-setup, preserving my existing profile. Keep judge=none for this test. Then build a tiny Python greeting function and a meaningful unittest in this disposable project. Record a project graph row with an observable file or command acceptance criterion. You may delegate implementation to engineer and an independent review to devops-lead using the installed roles; inherit my configured model. Show me the verification result and append a short local worklog entry. Do not mark the row done if verification fails. Tell me if a role, skill, hook or MCP tool is unavailable.

Expected: the team follows the Codex host instructions, uses the project graph/worklog, runs the test and records actual verification. The reviewer must be a separate agent if your host supports delegation; a self-review does not establish independent-audit acceptance. Confirm all four role files exist (`technical-cofounder`, `engineer`, `devops-lead`, `lead-fde`), and that the requested two roles can actually be selected. You can open the graph with `.hyperspace/env/bin/hyperspace serve --open`.

This conversation uses your configured Codex model/account. Enabling the optional Codex **judge** is a separate choice: authenticate the CLI, then rerun the step 2 provision command with `--judge codex`. Its model calls use your account. Do not report model-judge verification from a `none` run.

## 5. Send the reviewer a compact result

Report OS, `codex --version`, the TC source commit (`git -C ../tc-source rev-parse HEAD`), install/provision/doctor outcomes, discovered skills, role selection, both MCP statuses, hook trust/status, test result, graph state and worklog readback. Include any exact error and the step where it occurred; remove secrets and private paths before sharing.

For host-guard regressions, the source checkout provides `python3 -m unittest tests.test_codex -v` (run from `tc-source`). Those tests cover the third-failure warning, fifth-failure block, success reset, ambiguous results, thread isolation, Stop retry and the provenance gate. They do not replace this live session test. In particular, Codex has no separate failure event: failures that produce no PostToolUse event cannot be counted, and unknown result formats retain counters with a diagnostic.

If reinstalling, use the exact same source/project paths and command from step 2. The installer refuses locally edited managed files; preserve and reconcile those edits before an update. It will not silently merge them. Moving the project or upgrading/removing its system Python requires regenerating its absolute command paths. There is no automatic updater or uninstaller in this preview; keep the disposable project until the result has been reviewed.
