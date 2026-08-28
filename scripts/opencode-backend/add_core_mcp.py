#!/usr/bin/env python3
"""Expose the kirocrew-core/cron MCP servers to opencode sessions.

kiro-cli got them from its agent files' mcpServers; opencode reads its own
config. Both are stdio servers (kirocrew mcp-core / mcp-cron) that connect
back to the running gateway over loopback — opencode spawns them natively.
"""
import json
import pathlib

OPENCODE_JSON = pathlib.Path.home() / ".config/opencode/opencode.json"

cfg = json.loads(OPENCODE_JSON.read_text())
mcp = cfg.setdefault("mcp", {})
mcp["kirocrew-core"] = {
    "command": "/home/<user>/.kiro/crew-venv/bin/kirocrew",
    "args": ["mcp-core"],
}
mcp["kirocrew-cron"] = {
    "command": "/home/<user>/.kiro/crew-venv/bin/kirocrew",
    "args": ["mcp-cron"],
}
tmp = OPENCODE_JSON.with_suffix(".json.tmp")
tmp.write_text(json.dumps(cfg, indent=2))
tmp.replace(OPENCODE_JSON)
print("mcp servers added:", list(mcp.keys()))
