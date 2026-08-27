#!/usr/bin/env python3
"""Add kirocrew-knowledge as an opencode agent (same as research/heartbeat)."""
import json
import pathlib

KIRO_AGENTS = pathlib.Path.home() / ".kiro/agents"
OPENCODE_AGENT_DIR = pathlib.Path.home() / ".config/opencode/agent"
OPENCODE_JSON = pathlib.Path.home() / ".config/opencode/opencode.json"

NAME = "kirocrew-knowledge"
DESC = "Dedicated agent for knowledge extraction, categorization, and summarization."
MODEL = "deepseek/deepseek-v4-flash"

kiro = json.loads((KIRO_AGENTS / f"{NAME}.json").read_text())
prompt = (kiro.get("prompt") or "").strip()
assert prompt, "no prompt in kiro agent json"
md = (
    "---\n"
    f"description: {DESC}\n"
    f"mode: primary\n"
    f"model: {MODEL}\n"
    "---\n\n"
    f"{prompt}\n"
)
OPENCODE_AGENT_DIR.mkdir(parents=True, exist_ok=True)
(OPENCODE_AGENT_DIR / f"{NAME}.md").write_text(md)
print(f"wrote agent/{NAME}.md ({len(prompt)} chars)")

cfg = json.loads(OPENCODE_JSON.read_text())
agents = cfg.setdefault("agent", {})
agents[NAME] = {"description": DESC, "mode": "primary", "model": MODEL}
tmp = OPENCODE_JSON.with_suffix(".json.tmp")
tmp.write_text(json.dumps(cfg, indent=2))
tmp.replace(OPENCODE_JSON)
print("opencode.json updated")
