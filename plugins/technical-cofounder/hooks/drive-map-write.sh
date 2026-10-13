#!/bin/bash
# drive-map-write.sh — the PreToolUse Write hook: drive_map_write.py, beside
# this file, run with this computer's own Python by run-system-python.sh.
# hooks.json names this one file: Anthropic's plugin directory reads one path
# per command.
#
# Source: Nova Caelum (2026). License: Apache-2.0.

exec "${CLAUDE_PLUGIN_ROOT}/hooks/run-system-python.sh" "${CLAUDE_PLUGIN_ROOT}/hooks/drive_map_write.py"
