#!/usr/bin/env python3
"""Move kirocrew-research + kirocrew-heartbeat into opencode.

Reads the installed kiro agent JSONs (which carry the real system prompts),
writes opencode agent .md files (frontmatter + prompt body), and adds the
agents to ~/.config/opencode/opencode.json so the names resolve as opencode
modes (fixes "mode not found" on research/heartbeat spawns).
"""
import json
import pathlib

KIRO_AGENTS = pathlib.Path.home() / ".kiro/agents"
OPENCODE_AGENT_DIR = pathlib.Path.home() / ".config/opencode/agent"
OPENCODE_JSON = pathlib.Path.home() / ".config/opencode/opencode.json"

AGENTS = [
    (
        "kirocrew-research",
        "Autonomous research worker — runs one research cycle per turn in a Research Lab campaign loop.",
    ),
    (
        "kirocrew-heartbeat",
        "Unattended polling worker — runs one HeartbeatService task per cycle with a read-only toolset.",
    ),
]

MODEL = "deepseek/deepseek-v4-flash"

for name, fallback_desc in AGENTS:
    kiro = json.loads((KIRO_AGENTS / f"{name}.json").read_text())
    prompt = (kiro.get("prompt") or "").strip()
    assert prompt, f"{name}: no prompt in kiro agent json"
    desc = (kiro.get("description") or fallback_desc).strip().replace('"', "'")
    md = (
        "---\n"
        f"description: {desc}\n"
        f"mode: primary\n"
        f"model: {MODEL}\n"
        "---\n\n"
        f"{prompt}\n"
    )
    OPENCODE_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    (OPENCODE_AGENT_DIR / f"{name}.md").write_text(md)
    print(f"wrote {OPENCODE_AGENT_DIR / name}.md ({len(prompt)} chars)")

cfg = json.loads(OPENCODE_JSON.read_text())
agents = cfg.setdefault("agent", {})
for name, fallback_desc in AGENTS:
    agents[name] = {
        "description": fallback_desc,
        "mode": "primary",
        "model": MODEL,
    }
    print(f"added opencode.json agent {name}")
tmp = OPENCODE_JSON.with_suffix(".json.tmp")
tmp.write_text(json.dumps(cfg, indent=2))
tmp.replace(OPENCODE_JSON)
print("opencode.json updated")
