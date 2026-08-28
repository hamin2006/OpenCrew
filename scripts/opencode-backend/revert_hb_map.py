#!/usr/bin/env python3
"""Revert the heartbeat agent mapping now that kirocrew-heartbeat is an
opencode agent; drop the now-unused ACP_BACKEND_KAS import."""
import pathlib
import sys

GATEWAY = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/slack/gateway.py"
)

OLD = (
    "                # The kirocrew-heartbeat agent is a kiro-cli concept;\n"
    "                # opencode only knows its own modes, so a kiro-only name\n"
    '                # would fault set_mode with "mode not found". Use\n'
    "                # opencode's kirocrew-lite (its minimal assistant agent)\n"
    "                # on the kas backend — the read-only tool gating below\n"
    "                # (HEARTBEAT_SAFE_TOOLS) is what actually bounds the\n"
    "                # heartbeat, not the agent identity.\n"
    '                _hb_agent = (\n'
    '                    "kirocrew-lite"\n'
    "                    if KiroCrewConfig.load().agent.acp_backend == ACP_BACKEND_KAS\n"
    '                    else "kirocrew-heartbeat"\n'
    "                )\n"
    "                client, is_new, _resumed = await self.sessions.get_or_create(\n"
    "                    session_key,\n"
    "                    agent=_hb_agent,\n"
    "                )\n"
)

NEW = (
    "                # The kirocrew-heartbeat agent is now defined in opencode\n"
    "                # (agent/kirocrew-heartbeat.md), so the name resolves as a\n"
    "                # real mode. The read-only tool gating below\n"
    "                # (HEARTBEAT_SAFE_TOOLS) is what bounds the heartbeat.\n"
    "                client, is_new, _resumed = await self.sessions.get_or_create(\n"
    "                    session_key,\n"
    '                    agent="kirocrew-heartbeat",\n'
    "                )\n"
)

text = GATEWAY.read_text()
count = text.count(OLD)
if count != 1:
    print(f"FAIL: expected exactly 1 match, found {count}")
    sys.exit(1)
text = text.replace(OLD, NEW)

imp = "from kiro_crew.acp.types import ACP_BACKEND_KAS\n"
icount = text.count(imp)
if icount != 1:
    print(f"FAIL: import match {icount}")
    sys.exit(1)
text = text.replace(imp, "")

GATEWAY.write_text(text)
print("OK reverted")
