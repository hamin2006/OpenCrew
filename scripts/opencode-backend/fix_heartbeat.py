#!/usr/bin/env python3
"""Fix heartbeat (and other kiro-only agent spawns) on the opencode backend.

1. runtime._mode_available: opencode sessions advertise their selectable
   agents as the configOptions ``mode`` select (no ``modes`` key), so consult
   it — otherwise set_mode was attempted for agents opencode doesn't know.
2. _heartbeat_task: the kirocrew-heartbeat agent exists only on kiro-cli;
   on the kas (opencode) backend use kirocrew-lite (opencode's minimal
   assistant agent). The heartbeat's real bound is the gateway-side
   HEARTBEAT_SAFE_TOOLS approval gate, not the agent identity.
"""
import pathlib
import sys

WHEEL = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew"
)
RUNTIME = WHEEL / "acp/runtime.py"
GATEWAY = WHEEL / "slack/gateway.py"

EDITS = [
    # ── 1a: runtime._mode_available consults configOptions mode select ──
    (
        RUNTIME,
        "        ids, _current, advertised = parse_session_modes(resp)\n"
        "        if not advertised:\n"
        "            return True\n"
        "        return agent in ids\n",
        "        # opencode-style backends advertise their selectable agents as\n"
        "        # the configOptions ``mode`` select (their session responses\n"
        "        # carry no ``modes`` key). Consult it when present so set_mode\n"
        "        # only fires for an agent opencode actually knows.\n"
        "        config_options = resp.get(\"configOptions\")\n"
        "        if isinstance(config_options, list):\n"
        "            for opt in config_options:\n"
        "                if isinstance(opt, dict) and opt.get(\"id\") == \"mode\":\n"
        "                    options = opt.get(\"options\")\n"
        "                    if isinstance(options, list):\n"
        "                        ids = {\n"
        "                            str(o.get(\"value\"))\n"
        "                            for o in options\n"
        "                            if isinstance(o, dict) and o.get(\"value\")\n"
        "                        }\n"
        "                        return agent in ids\n"
        "        ids, _current, advertised = parse_session_modes(resp)\n"
        "        if not advertised:\n"
        "            return True\n"
        "        return agent in ids\n",
    ),
    # ── 2a: import ACP_BACKEND_KAS in the gateway ──
    (
        GATEWAY,
        "from kiro_crew.config import KiroCrewConfig\n",
        "from kiro_crew.acp.types import ACP_BACKEND_KAS\n"
        "from kiro_crew.config import KiroCrewConfig\n",
    ),
    # ── 2b: heartbeat agent selection ──
    (
        GATEWAY,
        "                client, is_new, _resumed = await self.sessions.get_or_create(\n"
        "                    session_key,\n"
        '                    agent="kirocrew-heartbeat",\n'
        "                )\n",
        "                # The kirocrew-heartbeat agent is a kiro-cli concept;\n"
        "                # opencode only knows its own modes, so a kiro-only name\n"
        "                # would fault set_mode with \"mode not found\". Use\n"
        "                # opencode's kirocrew-lite (its minimal assistant agent)\n"
        "                # on the kas backend — the read-only tool gating below\n"
        "                # (HEARTBEAT_SAFE_TOOLS) is what actually bounds the\n"
        "                # heartbeat, not the agent identity.\n"
        "                _hb_agent = (\n"
        '                    "kirocrew-lite"\n'
        "                    if KiroCrewConfig.load().agent.acp_backend == ACP_BACKEND_KAS\n"
        '                    else "kirocrew-heartbeat"\n'
        "                )\n"
        "                client, is_new, _resumed = await self.sessions.get_or_create(\n"
        "                    session_key,\n"
        "                    agent=_hb_agent,\n"
        "                )\n",
    ),
]

failures = 0
for path, old, new in EDITS:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL {path.name}: expected exactly 1 match, found {count} for: {old[:60]!r}")
        failures += 1
        continue
    backup = path.with_suffix(path.suffix + ".hbak")
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new))
    print(f"OK   {path.name}")

sys.exit(1 if failures else 0)
