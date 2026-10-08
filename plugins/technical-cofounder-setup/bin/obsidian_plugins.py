#!/usr/bin/env python3
"""Add the Obsidian viewers a user said yes to, from each author's own GitHub release.

    obsidian_plugins.py list
    obsidian_plugins.py install --project <absolute path> --plugin <id>

Nothing is bundled in the starter template, so nothing is redistributed: setup/obsidian-plugins.json
names a short list of plugins, each pinned to one release and to the SHA-256 of every file. `install`
downloads those files over plain HTTPS (no gh, no Git), refuses any file that is not the pinned one,
and only then puts them in <project>/.obsidian/plugins/<id>/ and the id in
<project>/.obsidian/community-plugins.json. A failure at any point leaves neither behind. A plugin
folder that is already there is never overwritten, and a plugin id that is not on the list is refused
before anything is fetched or created.

Every verb prints one JSON document on stdout. Exit 0: it did what was asked. Exit 1: the install
failed (the document says why). Exit 2: bad usage.

Standard library only. Python 3.11 or newer.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / "setup" / "obsidian-plugins.json"
RELEASE_URL = "https://github.com/%s/releases/download/%s/%s"
TIMEOUT_SECONDS = 60


class Usage(Exception):
    """The command line asked for something this script does not do."""


class Failed(Exception):
    """An install that could not finish; nothing was left behind."""


def fetch(url):
    """The bytes at `url`. Tests replace this; a real run uses plain HTTPS."""
    request = urllib.request.Request(url, headers={"User-Agent": "nc-setup"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def load_catalog(path):
    return {entry["id"]: entry for entry in json.loads(Path(path).read_text(encoding="utf-8"))["plugins"]}


def read_enabled(project):
    """(the path of community-plugins.json, the ids in it). A file that is not a list of ids is
    never rewritten: the install stops before it downloads anything."""
    path = project / ".obsidian" / "community-plugins.json"
    if not path.exists():
        return path, []
    try:
        listed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        listed = None
    if not (isinstance(listed, list) and all(isinstance(item, str) for item in listed)):
        raise Failed(
            "%s is not a list of plugin ids, so setup leaves it alone; fix it or move it aside, then ask again" % path
        )
    return path, listed


def download_into(stage, plugin, fetch_bytes):
    """Every pinned file into `stage`, each one checked against its pin."""
    for name, pinned in plugin["files"].items():
        url = RELEASE_URL % (plugin["repo"], plugin["tag"], name)
        try:
            data = fetch_bytes(url)
        except Exception as exc:   # any failure to download is the same answer: not installed
            raise Failed("could not download %s from %s: %s" % (name, url, exc))
        if hashlib.sha256(data).hexdigest() != pinned:
            raise Failed("%s does not match the copy setup checked (SHA-256), so nothing was installed" % name)
        (stage / name).write_bytes(data)


def install(plugins, project, plugin_id, fetch_bytes):
    plugin = plugins.get(plugin_id)
    if plugin is None:
        raise Usage("%s is not on the list of plugins setup can add" % plugin_id)
    project = Path(project)
    if not project.is_dir():
        raise Usage("%s is not a folder" % project)
    enabled_path, enabled = read_enabled(project)
    plugins_dir = project / ".obsidian" / "plugins"
    final = plugins_dir / plugin_id
    if final.exists():
        return 0, report(plugin, "already", final, enabled,
                         "%s is already in this project, and setup left it as it is." % plugin["name"])

    stage = plugins_dir / ("." + plugin_id + ".part")
    pending = enabled_path.with_name(enabled_path.name + ".part")
    listed = enabled if plugin_id in enabled else enabled + [plugin_id]
    try:
        plugins_dir.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(stage, ignore_errors=True)   # a leftover of an earlier run of this script
        stage.mkdir()
        download_into(stage, plugin, fetch_bytes)
        pending.write_text(json.dumps(listed, indent=2) + "\n", encoding="utf-8")
        os.replace(stage, final)
        try:
            os.replace(pending, enabled_path)
        except OSError:
            shutil.rmtree(final, ignore_errors=True)   # not listed means not installed
            raise
    except OSError as exc:
        raise Failed("could not write into %s: %s" % (project / ".obsidian", exc))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        pending.unlink(missing_ok=True)
    return 0, report(plugin, "installed", final, listed,
                     "%s is installed in this project and listed in community-plugins.json." % plugin["name"])


def report(plugin, result, path, enabled, detail):
    return {"command": "install", "plugin": plugin["id"], "result": result, "path": str(path),
            "enabled": enabled, "detail": detail}


def listing(plugins):
    keys = ("id", "name", "for", "licence", "repo", "tag")
    return {"command": "list", "plugins": [{key: entry[key] for key in keys} for entry in plugins.values()]}


def parse(argv):
    parser = argparse.ArgumentParser(prog="obsidian_plugins.py", description=__doc__.split("\n\n")[0])
    verbs = parser.add_subparsers(dest="verb", required=True)
    verbs.add_parser("list", help="the plugins setup can add, and what each is for")
    add = verbs.add_parser("install", help="add one plugin from that list to a project")
    add.add_argument("--project", required=True, help="absolute path of the project folder")
    add.add_argument("--plugin", required=True, help="a plugin id from `list`")
    return parser.parse_args(argv)


def main(argv=None, fetch=fetch, catalog=CATALOG):
    for stream in (sys.stdout, sys.stderr):   # Windows consoles default to a legacy code page
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        args = parse(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        plugins = load_catalog(catalog)
        if args.verb == "list":
            code, document = 0, listing(plugins)
        else:
            code, document = install(plugins, args.project, args.plugin, fetch)
    except Usage as exc:
        print("obsidian_plugins.py: %s" % exc, file=sys.stderr)
        return 2
    except Failed as exc:
        code, document = 1, {"command": "install", "plugin": args.plugin, "result": "failed", "detail": str(exc)}
    print(json.dumps(document, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
