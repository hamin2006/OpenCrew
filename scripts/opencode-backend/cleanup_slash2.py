#!/usr/bin/env python3
"""Fix the remaining /model cleanup (edit 1 re-anchored)."""
import pathlib
import sys

RUNNER = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_runner.py"
)

OLD = (
    "    provider = state.sessions.get_provider(session_key)\n"
    '    _cur = ""\n'
    "    if provider is not None:\n"
    '        _client = getattr(provider, "_client", None)\n'
    "        if _client is not None:\n"
    "            _opts = (\n"
    '                _client.acp_config_options()\n'
    '                if callable(getattr(_client, "acp_config_options", None))\n'
    '                else getattr(_client, "_config_options", None)\n'
    "            )\n"
    "            logger.warning(\n"
    '                "SLASHDBG client=%r opts=%r",\n'
    "                type(_client).__name__,\n"
    '                [o.get("id") if isinstance(o, dict) else None for o in (_opts or [])][:10],\n'
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
    '    elif first_word == "/usage":\n'
)

NEW = (
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
    '    elif first_word == "/usage":\n'
)

text = RUNNER.read_text()
count = text.count(OLD)
if count != 1:
    print(f"FAIL: expected exactly 1 match, found {count}")
    sys.exit(1)
RUNNER.write_text(text.replace(OLD, NEW))
print("OK")
