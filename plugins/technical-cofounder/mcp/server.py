#!/usr/bin/env python3
"""caelum-dev-team MCP server: JSON-RPC 2.0, newline-delimited, over stdio.

Standard library only, no network, no credentials. Exposes the worklog
tools (worklog_append / worklog_recent / worklog_search). Declared in
../.mcp.json, which starts this file as ${CLAUDE_PLUGIN_ROOT}/mcp/server.py.

When Hyperspace Engine holds the project's worklog (see ../bin/he_bridge.py),
the worklog tools go through its CLI instead of worklog.py and fail loud if it
is missing; otherwise worklog.py runs exactly as it always has.

Error handling: an unknown method returns a JSON-RPC error (-32601). A
tool exception is reported as a tool result with isError: true and the
message -- the server never exits on a bad call. Notifications (messages
with no "id") never get a reply, per JSON-RPC 2.0.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent / "bin"))

import he_bridge  # noqa: E402
import worklog  # noqa: E402

SERVER_NAME = "caelum-dev-team"
SERVER_VERSION = "0.1.0"

TOOLS = [
    {
        "name": "worklog_append",
        "description": "Append an entry to the project worklog (canonical markdown, derived CSV index; Hyperspace Engine's store when it holds this project's worklog).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Short summary, at most 280 characters."},
                "detail": {"type": "string", "description": "Optional long-form detail."},
                "author": {"type": "string", "description": "Who logged the entry. Defaults to 'agent'."},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Topical tags."},
                "root": {"type": "string", "description": "Project root. Defaults to CLAUDE_PROJECT_DIR, else cwd."},
            },
            "required": ["summary"],
        },
    },
    {
        "name": "worklog_recent",
        "description": "Return the N most recent worklog entries, newest first.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "How many entries. Defaults to 5."},
                "root": {"type": "string", "description": "Project root. Defaults to CLAUDE_PROJECT_DIR, else cwd."},
            },
            "required": [],
        },
    },
    {
        "name": "worklog_search",
        "description": "Search worklog entries (summary, detail, tags, author) for a query string.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to search for."},
                "root": {"type": "string", "description": "Project root. Defaults to CLAUDE_PROJECT_DIR, else cwd."},
            },
            "required": ["query"],
        },
    },
]


def _resolve_root(args):
    root = args.get("root") if isinstance(args, dict) else None
    if root:
        return root
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return env_root
    return os.getcwd()


def _worklog_for(root):
    """Hyperspace Engine's store when it holds this project's worklog, else TC's markdown."""
    return he_bridge if he_bridge.uses_store(root) else worklog


def _call_tool(name, args):
    args = args or {}
    if name == "worklog_append":
        root = _resolve_root(args)
        return _worklog_for(root).append(
            root,
            args["summary"],
            detail=args.get("detail", ""),
            author=args.get("author", "agent"),
            tags=args.get("tags", []),
        )
    if name == "worklog_recent":
        root = _resolve_root(args)
        return _worklog_for(root).recent(root, n=args.get("n", 5))
    if name == "worklog_search":
        root = _resolve_root(args)
        return _worklog_for(root).search(root, args["query"])
    raise ValueError(f"unknown tool {name!r}")


def _handle_initialize(params):
    params = params or {}
    return {
        "protocolVersion": params.get("protocolVersion"),
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    }


def _handle_tools_list(_params):
    return {"tools": TOOLS}


def _handle_tools_call(params):
    params = params or {}
    name = params.get("name")
    arguments = params.get("arguments") or {}
    try:
        result = _call_tool(name, arguments)
        return {"content": [{"type": "text", "text": json.dumps(result)}], "isError": False}
    except Exception as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}


def _handle_ping(_params):
    return {}


METHODS = {
    "initialize": _handle_initialize,
    "tools/list": _handle_tools_list,
    "tools/call": _handle_tools_call,
    "ping": _handle_ping,
}


def _dispatch(message):
    """Process one decoded JSON-RPC message. Returns a response dict, or None
    when no reply is due (a notification, or notifications/initialized)."""
    if not isinstance(message, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}

    is_notification = "id" not in message
    msg_id = message.get("id")
    method = message.get("method")

    if method == "notifications/initialized":
        return None

    handler = METHODS.get(method)
    if handler is None:
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

    try:
        result = handler(message.get("params"))
    except Exception as exc:
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": str(exc)}}

    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def serve(instream=None, outstream=None):
    instream = instream or sys.stdin
    outstream = outstream or sys.stdout
    for line in instream:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            outstream.write(
                json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}) + "\n"
            )
            outstream.flush()
            continue
        response = _dispatch(message)
        if response is not None:
            outstream.write(json.dumps(response) + "\n")
            outstream.flush()


if __name__ == "__main__":
    # Claude Code speaks UTF-8; Windows pipes default to the ANSI code page.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    serve()
