#!/usr/bin/env python3
"""Fix the dashboard model picker for opencode.

1. _wire_model_id: the picker sends the DISPLAY label (model_name/name), but
   opencode's set_model wants the provider/model wire id. Resolve the label
   (or wire id) against the session's configOptions model select before the
   registry passthrough — otherwise opencode rejects "model not found" and
   the handler falls back to a full session reset (which is what made /model
   report "No active session yet").
2. /model slash: when no live session, fall back to the slot's configured
   model instead of claiming there is none.
"""
import pathlib
import sys

HANDLERS = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_handlers.py"
)
RUNNER = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_runner.py"
)

EDITS = [
    (
        HANDLERS,
        "    return model_registry.to_acp_id(model_name)\n"
        "\n"
        "\n"
        "async def _reapply_effort_after_live_switch(\n",
        "    # opencode: the dashboard picker sends the DISPLAY label\n"
        "    # (model_name/name), but opencode's set_model wants the\n"
        "    # ``provider/model`` wire id. Resolve the label (or a wire id)\n"
        "    # against the session's configOptions model select — value is the\n"
        "    # wire id, name the display label (optionally suffixed\n"
        "    # \"Name (Provider)\" by the dashboard catalog).\n"
        '    _client = getattr(provider, "_client", None)\n'
        "    if _client is not None:\n"
        '        for _opt in getattr(_client, "_config_options", None) or []:\n'
        '            if isinstance(_opt, dict) and _opt.get("id") == "model":\n'
        '                for _o in _opt.get("options", []) or []:\n'
        "                    if not isinstance(_o, dict):\n"
        "                        continue\n"
        '                    _val = _o.get("value")\n'
        '                    _nm = _o.get("name")\n'
        "                    if not _val:\n"
        "                        continue\n"
        "                    if _val == model_name or (\n"
        "                        _nm\n"
        "                        and (_nm == model_name or model_name.startswith(f\"{_nm} (\"))\n"
        "                    ):\n"
        "                        return str(_val)\n"
        "                break\n"
        "    return model_registry.to_acp_id(model_name)\n"
        "\n"
        "\n"
        "async def _reapply_effort_after_live_switch(\n",
    ),
    (
        RUNNER,
        '    if first_word == "/model":\n'
        "        if _cur:\n"
        '            body = f"🧠 Current model: `{_cur}`\\nSwitch it from the model picker in the chat header."\n'
        "        else:\n"
        '            body = "No active session yet — send a message first. (Or use the model picker in the header.)"\n',
        '    if first_word == "/model":\n'
        "        if _cur:\n"
        '            body = f"🧠 Current model: `{_cur}`\\nSwitch it from the model picker in the chat header."\n'
        '        elif getattr(slot, "model", ""):\n'
        '            body = f"🧠 Current model: `{slot.model}` (no live session — the next message starts it)."\n'
        "        else:\n"
        '            body = "Auto (backend default) — no model picked yet. Send a message or use the model picker in the header."\n',
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
    backup = path.with_suffix(path.suffix + ".wmbak")
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new))
    print(f"OK   {path.name}")

sys.exit(1 if failures else 0)
