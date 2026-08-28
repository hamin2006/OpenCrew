#!/usr/bin/env python3
"""Wire /tools, /mcp, /logdump, /hooks into chat_runner.py (gateway-local).

Edits:
  1. _GATEWAY_SLASH_COMMANDS: add the 4 names
  2. _handle_gateway_slash: 4 branches calling kiro_crew.dashboard.slash_ops
     (lazy imports, matching the file's existing pattern); /mcp toggles
     reset the slot session via _reset_slot_session
  3. /help body: add the 4 lines
"""
import pathlib

PATH = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_runner.py"
)

EDITS = [
    (
        '        "/changelog",\n        "/todos",\n    }\n',
        '        "/changelog",\n        "/todos",\n        "/tools",\n'
        '        "/mcp",\n        "/logdump",\n        "/hooks",\n    }\n',
    ),
    (
        '        body = f"\U0001F4E6 Kiro Crew {_kcrew_version} (opencode backend)"\n'
        "    else:\n        return False, None\n",
        '        body = f"\U0001F4E6 Kiro Crew {_kcrew_version} (opencode backend)"\n'
        "    elif first_word == \"/tools\":\n"
        "        from kiro_crew.dashboard import slash_ops\n"
        "\n"
        "        body = slash_ops.handle_tools(agent=slot.agent)\n"
        "    elif first_word == \"/mcp\":\n"
        "        from kiro_crew.dashboard import slash_ops\n"
        "\n"
        "        body, _needs_reset = slash_ops.handle_mcp(_rest)\n"
        "        if _needs_reset:\n"
        "            from kiro_crew.dashboard.chat_handlers import _reset_slot_session\n"
        "\n"
        "            await _reset_slot_session(state, slot, session_key)\n"
        "    elif first_word == \"/logdump\":\n"
        "        from kiro_crew.dashboard import slash_ops\n"
        "\n"
        "        body = slash_ops.handle_logdump(_rest)\n"
        "    elif first_word == \"/hooks\":\n"
        "        from kiro_crew.dashboard import slash_ops\n"
        "\n"
        "        body = slash_ops.handle_hooks()\n"
        "    else:\n        return False, None\n",
    ),
    (
        '            "`/goal` — goal-driven loop\\n"\n'
        '            "`/prompts` — prompt library"\n',
        '            "`/goal` — goal-driven loop\\n"\n'
        '            "`/prompts` — prompt library\\n"\n'
        '            "`/tools` — available tools and MCP servers\\n"\n'
        '            "`/mcp` — MCP server status and toggles\\n"\n'
        '            "`/logdump` — tail the gateway log\\n"\n'
        '            "`/hooks` — hook events and wiring status"\n',
    ),
]

failures = 0
for old, new in EDITS:
    text = PATH.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        print(f"FAIL: expected exactly 1 match, found {count} for: {old[:60]!r}")
        failures += 1
        continue
    backup = PATH.with_suffix(PATH.suffix + ".slashopsbak")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    PATH.write_text(text.replace(old, new), encoding="utf-8")
    print("OK   edit applied")

raise SystemExit(1 if failures else 0)
