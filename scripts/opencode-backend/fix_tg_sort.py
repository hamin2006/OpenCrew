#!/usr/bin/env python3
"""Sort the telegram /model catalog so the session's current model/provider
are inside the 24-row window. opencode's catalog lists opencode/opencode-go
first, so the configured model (deepseek/deepseek-v4-flash, index 24) was
invisible. Current model -> its provider -> the rest, Auto always first."""
import pathlib
import sys

DISPATCH = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/telegram/transport_dispatch.py"
)

OLD = (
    "        if len(rows) <= 1 and str(getattr(provider, \"session_id\", \"\") or \"\").startswith(\"ses_\"):\n"
    "            rows = [(\"\", \"Auto (let the backend choose)\")]\n"
    "            rows.extend(await self._fetch_opencode_model_rows())\n"
    "        return tuple(rows[:_MODEL_PICKER_LIMIT])\n"
)

NEW = (
    "        if len(rows) <= 1 and str(getattr(provider, \"session_id\", \"\") or \"\").startswith(\"ses_\"):\n"
    "            rows = [(\"\", \"Auto (let the backend choose)\")]\n"
    "            rows.extend(await self._fetch_opencode_model_rows())\n"
    "            # opencode's catalog lists providers in an order that buries\n"
    "            # everything except opencode/opencode-go under the picker cap\n"
    "            # — the session's own model can sit just past the window.\n"
    "            # Put the current model and its provider first so the picker\n"
    "            # always shows what the session is actually running.\n"
    "            cur = \"\"\n"
    "            _client = getattr(provider, \"_client\", None)\n"
    "            if _client is not None:\n"
    "                for _opt in getattr(_client, \"_config_options\", None) or []:\n"
    "                    if isinstance(_opt, dict) and _opt.get(\"id\") == \"model\":\n"
    "                        _v = _opt.get(\"currentValue\")\n"
    "                        if isinstance(_v, str) and _v:\n"
    "                            cur = _v\n"
    "                        break\n"
    "                if not cur:\n"
    "                    cur = str(getattr(_client, \"_resolved_model_id\", \"\") or \"\").strip()\n"
    "            _prov = cur.split(\"/\", 1)[0] if cur else \"\"\n"
    "            if _prov:\n"
    "                rows.sort(\n"
    "                    key=lambda r: (\n"
    "                        (-1, r[0])\n"
    "                        if not r[0]\n"
    "                        else (\n"
    "                            (0, r[0])\n"
    "                            if r[0] == cur\n"
    "                            else ((1, r[0]) if r[0].split(\"/\", 1)[0] == _prov else (2, r[0]))\n"
    "                        )\n"
    "                    )\n"
    "                )\n"
    "        return tuple(rows[:_MODEL_PICKER_LIMIT])\n"
)

text = DISPATCH.read_text()
count = text.count(OLD)
if count != 1:
    print(f"FAIL: expected exactly 1 match, found {count}")
    sys.exit(1)
DISPATCH.write_text(text.replace(OLD, NEW))
print("OK sort added")
