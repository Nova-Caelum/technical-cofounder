"""Unit tests for the credential handling of plugins/super-novacaelum: the
research extras (Context7, Exa, Browserbase). A key typed into Claude Code's
secure prompt must reach each server in a request header, never in the web
address, where proxies, server logs and browser histories keep it.

Standard library only.
"""
import json
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
SUPER = REPO_ROOT / "plugins" / "super-novacaelum"
MCP = json.loads((SUPER / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
USER_CONFIG = json.loads((SUPER / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["userConfig"]

PLACEHOLDER = re.compile(r"\$\{user_config\.([A-Za-z0-9_]+)\}")
# Parameter names that read as credentials, whatever the value is.
CREDENTIAL_NAME = re.compile(r"key|token|secret|password|auth|bearer", re.IGNORECASE)


class KeysTravelInHeaders(unittest.TestCase):
    def test_no_server_address_carries_a_key(self):
        for name, server in MCP.items():
            url = server["url"]
            query = urlsplit(url).query
            with self.subTest(server=name):
                self.assertNotIn("user_config", query, f"{name}: a user_config value sits in the query string of {url}")
                names = [param for param, _ in parse_qsl(query, keep_blank_values=True)]
                self.assertEqual(
                    [param for param in names if CREDENTIAL_NAME.search(param)], [],
                    f"{name}: the query string of {url} has a credential-looking parameter",
                )

    def test_browserbase_sends_its_key_in_a_header(self):
        server = MCP["browserbase"]
        self.assertEqual(
            server.get("headers"), {"Authorization": "Bearer ${user_config.browserbase_api_key}"},
            "Browserbase must send the key as an Authorization bearer header",
        )

    def test_every_key_a_server_uses_is_a_declared_user_config_field(self):
        for name, server in MCP.items():
            used = set(PLACEHOLDER.findall(json.dumps(server)))
            with self.subTest(server=name):
                self.assertTrue(used, f"{name} uses no user_config key")
                self.assertLessEqual(used, set(USER_CONFIG), f"{name} uses a key plugin.json does not declare")


if __name__ == "__main__":
    unittest.main()
