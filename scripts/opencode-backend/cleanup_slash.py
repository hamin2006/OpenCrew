#!/usr/bin/env python3
"""Drop the configOptions dependency from /model and /agent.

slot.model is ALWAYS the current model (the pick API resolves labels to wire
ids and stores them), so /model just reads it — no live-handle configOptions
needed. Same for /agent. Removes the debug instrumentation.
"""
import pathlib
import sys

RUNNER = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_runner.py"
)
HANDLE = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/acp/session_handle.py"
)

EDITS = [
    # ── 1: drop the _cur configOptions block ──
    (
        RUNNER,
        "    provider = state.sessions.get_provider(session_key)\n"
        '    _cur = ""\n'
        "    if provider is not None:\n"
        '        _client = getattr(provider, "_client", None)\n'
        "        if _client is not None:\n"
        "            logger.warning(\n"
        '                "SLASHDBG client=%r opts=%r",\n'
        "                type(_client).__name__,\n"
        '                [o.get("id") if isinstance(o, dict) else None for o in (_opts or [])][:10],\n'
        "            )\n"
        "            _opts = (\n"
        '                _client.acp_config_options()\n'
        '                if callable(getattr(_client, "acp_config_options", None))\n'
        '                else getattr(_client, "_config_options", None)\n'
        "            )\n"
        "            for _opt in _opts or []:\n"
        '                if isinstance(_opt, dict) and _opt.get("id") == "model":\n'
        '                    _v = _opt.get("currentValue")\n'
        "                    if isinstance(_v, str) and _v:\n"
        "                        _cur = _v\n"
        "                    break\n"
        "            if not _cur:\n"
        '                _cur = str(getattr(_client, "_resolved_model_id", "") or "").strip()\n'
        "\n"
        '    if first_word == "/model":\n'
        "        if _cur:\n"
        '            body = f"🧠 Current model: `{_cur}`\\nSwitch it from the model picker in the chat header."\n'
        '        elif getattr(slot, "model", ""):\n'
        '            body = f"🧠 Current model: `{slot.model}` (no live session — the next message starts it)."\n'
        "        else:\n"
        '            body = "Auto (backend default) — no model picked yet. Send a message or use the model picker in the header."\n'
        '    elif first_word == "/usage":\n',
        "    provider = state.sessions.get_provider(session_key)\n"
        "\n"
        '    if first_word == "/model":\n'
        "        # slot.model is ALWAYS the current model: the pick API resolves\n"
        "        # picker labels to opencode wire ids before storing, so no live\n"
        "        # configOptions read is needed (and the live handle's options\n"
        "        # are not reliably populated on the pooled path).\n"
        '        if getattr(slot, "model", ""):\n'
        '            body = f"🧠 Current model: `{slot.model}`\\nSwitch it from the model picker in the chat header."\n'
        "        else:\n"
        '            body = "Auto (backend default) — no model picked yet. Send a message or use the model picker in the header."\n'
        '    elif first_word == "/usage":\n',
    ),
    # ── 2: simplify /agent to slot.agent ──
    (
        RUNNER,
        '    elif first_word == "/agent":\n'
        "        if _cur:\n"
        '            _modes: list[str] = []\n'
        '            _client = getattr(provider, "_client", None)\n'
        "            _opts = (\n"
        '                _client.acp_config_options()\n'
        '                if callable(getattr(_client, "acp_config_options", None))\n'
        '                else getattr(_client, "_config_options", None)\n'
        "            )\n"
        "            for _opt in _opts or []:\n"
        '                if isinstance(_opt, dict) and _opt.get("id") == "mode":\n'
        "                    _modes = [\n"
        '                        str(o.get("value"))\n'
        '                        for o in _opt.get("options", [])\n'
        "                        if isinstance(o, dict) and o.get(\"value\")\n"
        "                    ]\n"
        "                    break\n"
        '            body = f"🤖 Agent: `{slot.agent or \'kirocrew\'}`"\n'
        "            if _modes:\n"
        '                body += "\\nAvailable: " + ", ".join(f"`{m}`" for m in _modes)\n'
        "        else:\n"
        '            body = (\n'
        '                f"🤖 Agent: `{slot.agent or \'kirocrew\'}`\\n"\n'
        '                "(Switch agents from the selector in the chat header.)"\n'
        "            )\n",
        '    elif first_word == "/agent":\n'
        '        body = (\n'
        '            f"🤖 Agent: `{slot.agent or \'kirocrew\'}`\\n"\n'
        "            \"(Switch agents from the selector in the chat header.)\"\n"
        "        )\n",
    ),
    # ── 3: remove STORE_DBG from session_handle ──
    (
        HANDLE,
        "        config_options = resp.get(\"configOptions\")\n"
        '        logger.warning("STORE_DBG resp_keys=%r co=%r", list(resp.keys()), type(config_options).__name__)\n'
        "        if isinstance(config_options, list):\n",
        "        config_options = resp.get(\"configOptions\")\n"
        "        if isinstance(config_options, list):\n",
    ),
]

failures = 0
for path, old, new in EDITS:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL {path.name}: expected exactly 1 match, found {count}")
        failures += 1
        continue
    backup = path.with_suffix(path.suffix + ".clnbak")
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new))
    print(f"OK   {path.name}")

sys.exit(1 if failures else 0)
