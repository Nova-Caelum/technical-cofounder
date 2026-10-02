#!/usr/bin/env python3
"""Check that an agent registry matches the files it describes.

Usage:
    python3 check_registry.py [ROOT]

ROOT holds agents/ and registry/agents.json. It is a plugin's root (the default
is the plugin this script ships in) or a project's .claude/ folder, where the
new-agent skill registers the agents a project adds.

Every check runs and every failure is listed:
  - registry/agents.json parses and each entry has name, role, use_when,
    skills, mcp_tools and with_super
  - every role is one declared under "roles"
  - every registry agent has agents/<name>.md whose frontmatter name matches,
    and every agents/*.md is in the registry
  - every skill resolves to skills/<name>/SKILL.md in ROOT or in this plugin
  - every mcp_tool is served by one of this plugin's MCP servers, asked live
    over stdio with tools/list
  - each agent's file names every skill, MCP tool and super skill its entry
    lists, so the registry can't claim a tool the agent is never told to use
  - an orchestrator's file names every other agent in the registry
  - with_super names need no files, but when super-novacaelum sits beside this
    plugin they must exist there

Exit 0 when clean, 1 with one reason per line otherwise. Standard library only.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
FIELDS = {"name": str, "role": str, "use_when": str, "skills": list, "mcp_tools": list, "with_super": dict}


def frontmatter_name(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        m = re.match(r"^name:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip("'\"")
    return None


def served_mcp_tools(failures):
    """Ask each stdio server in this plugin's .mcp.json for its tools."""
    mcp_json = PLUGIN / ".mcp.json"
    if not mcp_json.is_file():
        failures.append(f"no {mcp_json.name} in {PLUGIN}, so no MCP tools can be served")
        return set()
    served = set()
    requests = "".join(json.dumps(m) + "\n" for m in (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "check_registry", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ))
    for server, cfg in json.loads(mcp_json.read_text(encoding="utf-8")).get("mcpServers", {}).items():
        if "command" not in cfg:
            continue  # not a local stdio server
        argv = [str(a).replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN)) for a in [cfg["command"], *cfg.get("args", [])]]
        try:
            env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN), "PYTHONDONTWRITEBYTECODE": "1"}
            out = subprocess.run(argv, input=requests, capture_output=True, text=True, timeout=15, env=env).stdout
            reply = next(r for r in map(json.loads, out.splitlines()) if r.get("id") == 2)
            served |= {t["name"] for t in reply["result"]["tools"]}
        except Exception as exc:  # fail closed: an unreachable server serves nothing
            failures.append(f"MCP server {server!r} did not list its tools ({type(exc).__name__}: {exc})")
    return served


def super_names(failures):
    """Skill and server names super-novacaelum ships, or None where it isn't beside us."""
    sup = PLUGIN.parent / "super-novacaelum"
    skills = {p.parent.name for p in (sup / "skills").glob("*/SKILL.md")} if (sup / "skills").is_dir() else None
    servers = None
    if (sup / ".mcp.json").is_file():
        try:
            servers = set(json.loads((sup / ".mcp.json").read_text(encoding="utf-8")).get("mcpServers", {}))
        except ValueError as exc:
            failures.append(f"super-novacaelum/.mcp.json is not valid JSON ({exc})")
    return skills, servers


def check(root):
    failures, lines = [], []
    reg_path = root / "registry" / "agents.json"
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
        agents = reg["agents"]
        assert isinstance(agents, list)
    except Exception as exc:
        return [f"{reg_path}: not a readable registry ({type(exc).__name__}: {exc})"], lines, 0

    roles = reg.get("roles", {})
    names = [a.get("name") for a in agents if isinstance(a, dict)]
    if len(names) != len(set(names)):
        failures.append("an agent is listed more than once")

    skill_dirs = [root / "skills", PLUGIN / "skills"]

    wanted_tools = {t for a in agents if isinstance(a, dict) for t in a.get("mcp_tools", [])}
    served = served_mcp_tools(failures) if wanted_tools else set()
    sup_skills, sup_servers = super_names(failures)

    for a in agents:
        if not isinstance(a, dict):
            failures.append(f"registry entry is not an object: {a!r}")
            continue
        name = a.get("name", "?")
        for field, kind in FIELDS.items():
            value = a.get(field)
            if not isinstance(value, kind) or (kind is str and not value.strip()):
                failures.append(f"{name}: field {field!r} missing, empty or not a {kind.__name__}")
        if a.get("role") not in roles:
            failures.append(f"{name}: role {a.get('role')!r} is not declared under \"roles\"")

        ws = a.get("with_super", {}) if isinstance(a.get("with_super"), dict) else {}
        f = root / "agents" / f"{name}.md"
        if not f.is_file():
            failures.append(f"{name}: no agents/{name}.md")
        else:
            body = f.read_text(encoding="utf-8")
            fm = frontmatter_name(body)
            if fm != name:
                failures.append(f"{name}: agents/{name}.md frontmatter name is {fm!r}")
            for listed in [*a.get("skills", []), *a.get("mcp_tools", []), *ws.get("skills", [])]:
                if f"`{listed}`" not in body:
                    failures.append(f"{name}: registry lists {listed!r} but agents/{name}.md never names it")
            if a.get("role") == "orchestrator":
                for other in names:
                    if other != name and not re.search(r"(?:`|:)" + re.escape(str(other)) + r"(?![\w-])", body):
                        failures.append(f"{name}: orchestrator file never names agent {other!r}")

        for skill in a.get("skills", []):
            if not any((d / skill / "SKILL.md").is_file() for d in skill_dirs):
                failures.append(f"{name}: skill {skill!r} not found under skills/")
        for tool in a.get("mcp_tools", []):
            if tool not in served:
                failures.append(f"{name}: MCP tool {tool!r} is not served by this plugin")

        for skill in ws.get("skills", []):
            if sup_skills is not None and skill not in sup_skills:
                failures.append(f"{name}: super skill {skill!r} not shipped by super-novacaelum")
        for server in ws.get("mcp_servers", []):
            if sup_servers is not None and server not in sup_servers:
                failures.append(f"{name}: super server {server!r} not declared by super-novacaelum")

        lines.append(
            f"  {name:<22} {str(a.get('role')):<18} {len(a.get('skills', [])):>2} skills  "
            f"{len(a.get('mcp_tools', [])):>2} MCP tools  +super: {len(ws.get('skills', []))} skills, {len(ws.get('mcp_servers', []))} servers"
        )

    for f in sorted((root / "agents").glob("*.md")):
        if f.stem not in names:
            failures.append(f"agents/{f.name} is not in the registry")

    if served:
        lines.append(f"  MCP tools served: {', '.join(sorted(served))}")
    return failures, lines, len(names)


def main(argv):
    if len(argv) > 2:
        sys.stderr.write("usage: check_registry.py [ROOT]\n")
        return 1
    root = Path(argv[1]).expanduser().resolve() if len(argv) == 2 else PLUGIN
    failures, lines, count = check(root)
    print(f"registry: {root / 'registry' / 'agents.json'}")
    print("\n".join(lines))
    if failures:
        print(f"REGISTRY FAIL: {len(failures)} problem(s)")
        print("\n".join(f"  - {x}" for x in failures))
        return 1
    print(f"REGISTRY OK: {count} agents")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
