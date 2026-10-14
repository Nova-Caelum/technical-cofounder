#!/usr/bin/env python3
"""Generate a project-scoped Codex installation from shared TC + pinned HSE sources.

Standard library only, Python >=3.11. Does not download, provision, grant trust,
change global configuration, or overwrite local edits. Run --help for inputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib

REPO = Path(__file__).resolve().parents[1]
ENGINE_REV = '45472d4260b65ecec1f194bdd044fba9880f42e4'
MANIFEST = '.codex/technical-cofounder-install.json'
RUNTIME = '.codex/technical-cofounder'
BEGIN = '# BEGIN TECHNICAL COFOUNDER (generated)'
END = '# END TECHNICAL COFOUNDER'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def frontmatter(text):
    match = re.match(r'^---\n(.*?)\n---\n(.*)', text, re.S)
    if not match:
        raise ValueError('Expected simple name/description frontmatter')
    fields = dict(re.findall(r'^(name|description): (.+)$', match[1], re.M))
    return fields, match[2].lstrip()


def translate(text, root):
    text = text.replace('${CLAUDE_PLUGIN_ROOT}', str(root))
    text = text.replace('/technical-cofounder-setup:start', '$tc-setup')
    text = re.sub(r'/?(?:technical-cofounder|hyperspace-engine):([\w-]+)', r'\1', text)
    text = text.replace('.claude/registry/agents.json', '.codex/technical-cofounder/technical-cofounder/registry/agents.json')
    return text


def safe_target(project, relative):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe managed path: ' + str(relative))
    target = project / relative
    for parent in [target, *target.parents]:
        if parent == project:
            break
        if parent.is_symlink():
            raise ValueError('Refusing symlink: ' + str(parent))
    if target.exists() and not target.is_file():
        raise ValueError('Expected a file: ' + str(target))
    return target


def block(existing, content):
    if BEGIN in existing or END in existing:
        if existing.count(BEGIN) != 1 or existing.count(END) != 1:
            raise ValueError('Malformed Technical Cofounder managed block')
        start, finish = existing.index(BEGIN), existing.index(END) + len(END)
        if finish < start:
            raise ValueError('Reversed managed block')
        return existing[:start] + BEGIN + '\n' + content.rstrip() + '\n' + END + existing[finish:]
    return existing.rstrip() + ('\n\n' if existing.strip() else '') + BEGIN + '\n' + content.rstrip() + '\n' + END + '\n'


def tracked(root, prefix=''):
    return git(root, 'ls-files', '-z', '--', *([prefix] if prefix else [])).split('\0')


def build(project, engine, python):
    if git(engine, 'rev-parse', 'HEAD') != ENGINE_REV or git(engine, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Engine source must be clean at pinned revision ' + ENGINE_REV)
    files, modes, starters = {}, {}, {}
    def add(path, data, mode=0o644):
        files[path] = data.encode() if isinstance(data, str) else data
        modes[path] = mode
    def snapshot(source, prefix, destination):
        for rel in tracked(source, prefix):
            if not rel:
                continue
            src = source / rel
            if src.is_symlink() or not src.is_file():
                raise ValueError('Source is not a regular tracked file: ' + str(src))
            short = str(Path(rel).relative_to(prefix)) if prefix else rel
            if not prefix and not (Path(short).parts[0] in ('hyperspace', 'bin', 'hooks', 'skills') or short.startswith('ui/dist/') or short in ('pyproject.toml', 'README.md', 'LICENSE')):
                continue
            add(destination + '/' + short, src.read_bytes(), 0o755 if os.access(src, os.X_OK) else 0o644)
    snapshot(REPO, 'plugins/technical-cofounder', RUNTIME + '/technical-cofounder')
    snapshot(engine, '', RUNTIME + '/hyperspace-engine')
    add(RUNTIME + '/adapter.py', (REPO / 'codex/adapter.py').read_bytes())
    contract = (REPO / 'codex/host-contract.md').read_text()
    add(RUNTIME + '/host-contract.md', contract)
    tc = project / RUNTIME / 'technical-cofounder'
    he = project / RUNTIME / 'hyperspace-engine'
    for source, installed in [(REPO / 'plugins/technical-cofounder', tc), (engine, he)]:
        repo_root = REPO if source.is_relative_to(REPO) else source
        skill_prefix = str((source / 'skills').relative_to(repo_root))
        for source_rel in sorted(tracked(repo_root, skill_prefix)):
            if not source_rel:
                continue
            src = repo_root / source_rel
            if src.is_symlink() or not src.is_file():
                raise ValueError('Skill source is not a regular tracked file: ' + str(src))
            rel = '.agents/skills/' + str(src.relative_to(source / 'skills'))
            if src.suffix == '.md':
                text = translate(src.read_text(), installed)
                if src.name == 'SKILL.md':
                    close = text.index('\n---', 4) + 4
                    text = text[:close] + '\n\n' + contract + '\n' + text[close:]
                add(rel, text)
            elif src.suffix == '.json':
                def render(value):
                    if isinstance(value, str):
                        return translate(value, installed)
                    if isinstance(value, list):
                        return [render(v) for v in value]
                    if isinstance(value, dict):
                        return {k: render(v) for k, v in value.items()}
                    return value
                add(rel, json.dumps(render(json.loads(src.read_text())), indent=2) + '\n')
            else:
                add(rel, src.read_bytes(), 0o755 if os.access(src, os.X_OK) else 0o644)
    personas = {}
    for src in sorted((REPO / 'plugins/technical-cofounder/agents').glob('*.md')):
        fields, body = frontmatter(src.read_text())
        body = contract + '\n' + translate(body, tc)
        personas[fields['name']] = body
        add('.codex/agents/' + fields['name'] + '.toml', '\n'.join(
            key + ' = ' + json.dumps(value, ensure_ascii=False) for key, value in
            [('name', fields['name']), ('description', fields['description']), ('developer_instructions', body)]) + '\n')
    def existing(rel):
        target = safe_target(project, rel)
        return target.read_text() if target.exists() else ''
    agents = existing('AGENTS.md')
    rules = []
    template = REPO / 'plugins/technical-cofounder-setup/template'
    for rule in sorted((template / '.claude/rules').glob('*.md')):
        rules.append(re.sub(r'^---\n.*?\n---\n', '', rule.read_text(), flags=re.S))
    add(RUNTIME + '/workspace-rules.md', '\n\n'.join(rules))
    merged_agents = block(agents, personas['technical-cofounder'])
    if len(merged_agents.encode()) > 32768:
        raise ValueError('Combined AGENTS.md exceeds the default Codex 32768-byte budget; move detailed rules into explicitly referenced files before installing')
    add('AGENTS.md', merged_agents)
    adapter = project / RUNTIME / 'adapter.py'
    command = [str(python), '-I', str(adapter)]
    config = existing('.codex/config.toml')
    parsed = tomllib.loads(config)
    if BEGIN not in config and any(n in parsed.get('mcp_servers', {}) for n in ('caelum-dev-team', 'hyperspace')):
        raise ValueError('MCP server name collision in .codex/config.toml')
    entries = []
    for name, server in [('caelum-dev-team', 'team'), ('hyperspace', 'hyperspace')]:
        entries.append('\n'.join(['[mcp_servers.' + name + ']', 'command = ' + json.dumps(str(python)),
            'args = ' + json.dumps(command[1:] + ['mcp', '--project', str(project), '--server', server]),
            'cwd = ' + json.dumps(str(project)), 'startup_timeout_sec = 30']))
    add('.codex/config.toml', block(config, '\n\n'.join(entries)))
    hooks_text = existing('.codex/hooks.json')
    hooks = json.loads(hooks_text) if hooks_text else {'hooks': {}}
    if not isinstance(hooks.get('hooks'), dict):
        raise ValueError('Expected hooks object in .codex/hooks.json')
    # Previous installation's exact commands are identified by this fixed adapter path.
    for event in ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'Stop'):
        groups = hooks['hooks'].setdefault(event, [])
        for group in groups:
            group['hooks'] = [h for h in group['hooks'] if str(adapter) not in shlex.split(h.get('command', ''))]
        hooks['hooks'][event] = [g for g in groups if g['hooks']]
        actions = ['hook', 'freshness'] if event == 'SessionStart' else ['hook']
        for action in actions:
            group = {'hooks': [{'type': 'command', 'command': shlex.join(command + [action, '--project', str(project)]), 'timeout': 60}]}
            if event in ('PreToolUse', 'PostToolUse'):
                group['matcher'] = '*'
            hooks['hooks'][event].append(group)
    add('.codex/hooks.json', json.dumps(hooks, indent=2) + '\n')
    provision = shlex.join(command + ['provision', '--project', str(project), '--judge', 'none'])
    add('.agents/skills/tc-setup/SKILL.md', '''---
name: tc-setup
description: Set up or diagnose the Technical Cofounder team and Hyperspace environment in this local Codex project.
---
''' + contract + '\n## Setup\n\nRead core_text/user.md (or the existing root user.md) and fill it in with the user. Preserve existing content.\n\n'
        + 'Provision the shared engine only when setup is requested, with this command:\n\n```sh\n' + provision + '\n```\n\n'
        + 'This downloads Python packages into .hyperspace/env and records provenance. It uses judge=none, so no paid model calls occur. Deterministic criteria work; LLM criteria are unavailable until the user explicitly selects and authenticates the Codex judge. Do not claim a live verifier pass with judge=none. For Codex judge use the same command with --judge codex after `codex login`. Review /hooks, trust the project and hook definitions yourself, then start a new local session. Use `codex mcp list` and both MCP servers to verify connectivity. Never run the Claude setup installer.\n')
    # Host-specific skill replacements retain the shared original as reference.
    for skill, guidance in {
        'new-agent': 'Read the shared specification in shared-policy.md for persona scope and quality gates. Create a native .codex/agents/<name>.toml with name, description and developer_instructions; do not set a model unless requested. Use the installed roles as examples. Validate with Python tomllib, then discover/select it in a fresh Codex session. Do not run the Claude Markdown registry generator or write .claude files. An independent audit is still required.',
        'hyperspace-setup': 'Use $tc-setup for this Codex project. It provisions the pinned shared engine with an explicit judge choice, without probing Claude. After provisioning, run `.hyperspace/env/bin/hyperspace doctor` and optionally `.hyperspace/env/bin/hyperspace serve --open`. Read shared-policy.md for background only; do not execute its Claude installation or automatic judge probing instructions.',
        'super-setup': 'Optional super connectors are not installed by this Codex distribution. Read shared-policy.md as a service inventory, not executable setup. Explain the core manual fallbacks. If the user wants an external service, consult its current official Codex MCP instructions, prepare configuration, and obtain any required account/credential authorization. Never run claude plugin install. Do not claim these connectors are verified by the core friend test.'
    }.items():
        rel = '.agents/skills/' + skill + '/SKILL.md'
        if rel not in files:  # Minimal source fixtures may omit optional skills.
            continue
        original = files[rel].decode()
        add('.agents/skills/' + skill + '/shared-policy.md', original)
        fields, _ = frontmatter(original)
        add(rel, '---\nname: ' + fields['name'] + '\ndescription: ' + fields['description'] + '\n---\n\n' + contract + '\n' + guidance + '\n')
    for src in sorted(template.rglob('*')):
        rel = src.relative_to(template)
        if not src.is_file() or rel.parts[0] not in ('core_text', 'work', 'worklog', 'reference'):
            continue
        target = safe_target(project, rel)
        if not target.exists() and not (str(rel) == 'core_text/user.md' and (project / 'user.md').exists()):
            starters[str(rel)] = translate(src.read_text(), tc).encode()
    return files, modes, starters


def install(project, engine, python):
    if sys.platform == 'win32':
        raise ValueError('This first Codex installer supports macOS/Linux only')
    project, engine, python = project.resolve(), engine.resolve(), python.resolve()
    if not python.is_file() or sys.prefix != sys.base_prefix:
        raise ValueError('Run with a system Python >=3.11, outside a project virtualenv')
    missing = [name for name in ('git', 'bash', 'jq') if not shutil.which(name)]
    if missing:
        raise ValueError('Required tools are missing: ' + ', '.join(missing))
    manifest_path = safe_target(project, MANIFEST)
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'files': {}}
    if not manifest_path.exists():
        for rel in ('AGENTS.md', '.codex/config.toml'):
            path = safe_target(project, rel)
            if path.exists() and (BEGIN in path.read_text() or END in path.read_text()):
                raise ValueError('Managed block without installation manifest: ' + rel)
    for rel, entry in old['files'].items():
        path = safe_target(project, rel)
        if not path.is_file() or digest(path.read_bytes()) != entry['sha256']:
            raise ValueError('Managed file changed locally; preserve/reconcile it before reinstall: ' + rel)
    files, modes, starters = build(project, engine, python)
    for rel, data in files.items():
        path = safe_target(project, rel)
        if path.exists() and rel not in old['files'] and rel not in ('AGENTS.md', '.codex/config.toml', '.codex/hooks.json'):
            raise ValueError('Unmanaged file collision: ' + rel)
    manifest = {'format': 1, 'tc_revision': git(REPO, 'rev-parse', 'HEAD'), 'engine_revision': ENGINE_REV,
                'files': {rel: {'sha256': digest(data), 'mode': modes[rel]} for rel, data in sorted(files.items())}}
    # Preflight has finished before the first write. Individual writes are atomic;
    # manifest is last, so interruption is detectable rather than silently blessed.
    for rel, data in {**files, **starters, MANIFEST: (json.dumps(manifest, indent=2) + '\n').encode()}.items():
        path = safe_target(project, rel)
        if path.exists() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, scratch = tempfile.mkstemp(dir=path.parent, prefix='.tc-install-')
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(data)
            os.chmod(scratch, modes.get(rel, 0o644))
            os.replace(scratch, path)
        finally:
            if os.path.exists(scratch):
                os.unlink(scratch)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--engine-source', type=Path, required=True, help='clean HSE checkout at ' + ENGINE_REV)
    args = parser.parse_args()
    try:
        manifest = install(args.project, args.engine_source, Path(sys.executable))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, 'Install refused: ' + str(exc) + '\n')
    print('Installed %d managed files. Next: review project configuration, run $tc-setup, and review /hooks.' % len(manifest['files']))


if __name__ == '__main__':
    main()
