# Technical Cofounder Agent

**A senior technical team for Claude Code.** A technical cofounder orchestrator, an engineer who builds it, a DevOps lead who audits it, and a forward-deployed engineer who gets you set up. Built to work in tandem to provide technical support through design, development, and implementation of whatever you hope to build. They come with deeply rooted governance mechanisms that enable state-aware workflow automation, independent completion verification, and anti-hallucination mechanisms built in by default.

> For vibe coders and non-technical founders: all the senior-engineer paranoia, none of the cap-table drama.

[![CI](https://github.com/Nova-Caelum/technical-cofounder/actions/workflows/ci.yml/badge.svg)](https://github.com/Nova-Caelum/technical-cofounder/actions/workflows/ci.yml) ![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)

## Install

Run these from your project folder. The team is installed for this project only, so your other projects stay as they are.

```bash
claude plugin marketplace add Nova-Caelum/technical-cofounder --scope project
claude plugin install base-novacaelum@technical-cofounder --scope project
```

Then open Claude Code in your project and say **"set me up"**. The setup skill asks two questions:
- Do you use Obsidian? If yes, you get a ready-made filesystem with 
- Do you want the super plugin? which provides enhancement to core functions through a suite curated tools we love and use everyday. 
  
It then adds the rules, a short profile of how you work, a worklog and templates, never overwriting your files.

**Optional: `super-novacaelum`.** An additional add-on plugin that take the agents capabilities to the next level. The suite includes agentic-enhanced web search (Exa), a cloud browser for better agent use of the web (Browserbase), and master instruction manual for hundreds of tools, languages, platforms so the technical agents stay up to date. MCPs and Nova Caelum authored companion skills to better help your agent use them. These tools are free to marginal cost, but require extra user setup to create accounts and download API keys for the services. Optional but encouraged. Your new forward-deployment engineer would be thrilled to help you set it up. 

```bash
claude plugin install super-novacaelum@technical-cofounder --scope project
```

**Needs:** Claude Code, `git` and `python3`. Super also needs Node.js.

## The team

| Agent | Role | Reach for it when |
|---|---|---|
| `technical-cofounder` *(default)* | Orchestrator: frames the problem, weighs options, runs the loop, routes work | You have a goal, not a task |
| `engineer` | Builder: writes the test first, then the code; never grades its own work | Something needs to exist |
| `devops-lead` | Auditor: checks every "done" against evidence, reviews diffs, runs the leak and quality checks | Something claims to be finished |
| `lead-fde` | Forward-deployed engineer: setup, onboarding, teaching, first-run fixes | You're new, stuck, or setting up |

`plugins/base-novacaelum/registry/agents.json` maps every agent to its skills and tools, and a check keeps that map honest.

## What's inside, and why each piece exists

Every mechanism here exists because we watched an agent fail without it.

| Piece | What it does | The failure it prevents |
|---|---|---|
| **The loop**: understand → decide → draft → build → live | Each stage ends at a gate that reads a file, not a feeling. Tests are written before the design, and the design is cut against them | Plans that never became work; architectures designed before anyone wrote down what "done" means |
| **Verifier** (local tool `verify`) | Checks typed acceptance criteria against your files (a file exists or contains something, tests pass, a human signed off), fails closed, and writes a verdict with evidence | "Done" claimed on a green status line while nothing actually changed |
| **An auditor separate from the builder** | `devops-lead` checks `engineer`'s claims | An agent grading its own homework |
| **Guardrail hooks** | A word budget per reply; a circuit breaker that stops the fifth identical failing retry; a session preload that brings back your profile and recent worklog | Padding; retry loops that burn an afternoon; every session starting from zero |
| **Five rules**: frame discipline, anti-hallucination, act-and-disclose, eliminate-first, anti-truncation | Each ships with a table of the excuses agents use to skip it, and the answer to each | Rules that read well and get rationalized away |
| **Engineering skills**: assumption check, verification before completion, overbloat review, architecture records, code review, option generation, stress testing | Senior judgment on demand | Building on a false premise; building the first idea; adding surface nobody needed |
| **Authoring kit**: `new-agent`, `pressure-scenario-skill-authoring`, templates | Grow your own team with the same discipline. A gate asks "does this need its own agent?", and every skill starts from three observed failures | A folder of agents nobody uses and skills that encode a hunch |
| **Local worklog** (tools `worklog_*`) | Markdown entries you own, with CSV and Obsidian views | Losing what was decided, and why, between sessions |

## How it was built

This repository was built with the loop it ships. [`examples/toy-run/`](examples/) is a real run folder. It walks a small goal through every stage: the problem, the tests, the decision, the plan and the verifier's verdicts.

## Roadmap

- **A hosted option for super:** one Nova Caelum key instead of three vendor keys
- **Feedback from `lead-fde`:** send us what broke, with one command
- An engineering-practice compiler skill and a context-window meter
- A verifier that can also judge prose, using a model

## Credits and license

Apache-2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE). Parts are adapted from [obra/superpowers](https://github.com/obra/superpowers), [mattpocock/skills](https://github.com/mattpocock/skills), [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) and our own [no-mistakes](https://github.com/Nova-Caelum/no-mistakes), all MIT; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Built by [Nova Caelum](https://novacaelum.com) for those without enterprise budgets.
