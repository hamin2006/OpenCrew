#!/usr/bin/env python3
"""Resolve picker labels to wire ids at the model-pick API.

The dashboard picker sends the DISPLAY label ("Name (Provider)"); opencode's
set_model wants provider/model. A raw label fails the live switch AND poisons
slot.model for the next spawn (handle.set_model(label) at session init). Fix
it at the single choke point: api_chat_slot_model resolves labels via the live
provider's configOptions, else the cached opencode catalog.
"""
import pathlib
import sys

HANDLERS = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_handlers.py"
)

# ── 1: helpers + constants before api_chat_slot_model ──
HELPERS_OLD = "async def api_chat_slot_model(request: web.Request) -> web.Response:\n"
HELPERS_NEW = (
    "_OPENCODE_MODEL_CATALOG: " "tuple[dict[str, str], float] | None" " = None\n"
    "_OPENCODE_MODEL_CATALOG_TTL = 300.0\n"
    "\n"
    "\n"
    "async def _opencode_model_catalog() -> dict[str, str]:\n"
    '    """label/wire -> wire id map from ``opencode models --verbose`` (cached)."""\n'
    "    global _OPENCODE_MODEL_CATALOG\n"
    "    _now = time.time()\n"
    "    if (\n"
    "        _OPENCODE_MODEL_CATALOG is not None\n"
    "        and _now - _OPENCODE_MODEL_CATALOG[1] < _OPENCODE_MODEL_CATALOG_TTL\n"
    "    ):\n"
    "        return _OPENCODE_MODEL_CATALOG[0]\n"
    "    _bin = \"/home/<user>/.opencode/bin/opencode\"\n"
    "    _PROVIDER_DISPLAY = {\n"
    '        "opencode": "OpenCode",\n'
    '        "opencode-go": "OpenCode Go",\n'
    '        "deepseek": "DeepSeek",\n'
    '        "openai": "OpenAI",\n'
    '        "groq": "Groq",\n'
    '        "moonshotai": "Moonshot AI",\n'
    '        "github-copilot": "GitHub Copilot",\n'
    "    }\n"
    '    _mapping: dict[str, str] = {}\n'
    "    try:\n"
    "        import json as _json\n"
    "        import subprocess as _subprocess\n"
    "\n"
    "        from kiro_crew.sandbox import create_subprocess_limited\n"
    "\n"
    "        _proc = await create_subprocess_limited(\n"
    "            _bin,\n"
    '            "models",\n'
    '            "--verbose",\n'
    "            stdout=_subprocess.PIPE,\n"
    "            stderr=_subprocess.PIPE,\n"
    "            start_new_session=True,\n"
    "        )\n"
    "        try:\n"
    "            _out, _err = await asyncio.wait_for(_proc.communicate(), timeout=15)\n"
    "        except asyncio.TimeoutError:\n"
    "            try:\n"
    "                _proc.kill()\n"
    "            except ProcessLookupError:\n"
    "                pass\n"
    "            await _proc.communicate()\n"
    "            return _mapping\n"
    "        if _proc.returncode != 0 or not _out.strip():\n"
    "            return _mapping\n"
    '        _buf = ""\n'
    '        for _line in _out.decode(errors="replace").splitlines():\n'
    '            if _line.lstrip().startswith("{"):\n'
    "                _buf = _line\n"
    "                continue\n"
    "            if _buf:\n"
    '                _buf += "\\n" + _line\n'
    "                try:\n"
    "                    _m = _json.loads(_buf)\n"
    "                except _json.JSONDecodeError:\n"
    "                    continue\n"
    '                _buf = ""\n'
    "                if not isinstance(_m, dict):\n"
    "                    continue\n"
    '                _mid = _m.get("id")\n'
    '                _pid = _m.get("providerID")\n'
    "                if not isinstance(_mid, str) or not isinstance(_pid, str):\n"
    "                    continue\n"
    '                _wire = f"{_pid}/{_mid}"\n'
    "                _mapping[_wire] = _wire\n"
    '                _nm = str(_m.get("name") or _mid)\n'
    "                _mapping[_nm] = _wire\n"
    '                _mapping[f"{_nm} ({_PROVIDER_DISPLAY.get(_pid, _pid)})"] = _wire\n'
    "    except Exception:\n"
    '        logger.warning("opencode model catalog resolve failed", exc_info=True)\n'
    "    if _mapping:\n"
    "        _OPENCODE_MODEL_CATALOG = (_mapping, time.time())\n"
    "    return _mapping\n"
    "\n"
    "\n"
    "async def _resolve_wire_model_id(label: str, provider: Any) -> str:\n"
    '    """Map a picker display label to opencode\'s provider/model wire id.\n'
    "\n"
    "    Prefers the live session's configOptions (value = wire id, name =\n"
    "    label); falls back to the cached catalog for cold sessions.\n"
    '    """\n'
    "    if provider is not None:\n"
    '        _client = getattr(provider, "_client", None)\n'
    "        if _client is not None:\n"
    "            _opts = (\n"
    '                _client.acp_config_options()\n'
    '                if callable(getattr(_client, "acp_config_options", None))\n'
    '                else getattr(_client, "_config_options", None)\n'
    "            )\n"
    "            for _opt in _opts or []:\n"
    '                if isinstance(_opt, dict) and _opt.get("id") == "model":\n'
    '                    for _o in _opt.get("options", []) or []:\n'
    "                        if not isinstance(_o, dict):\n"
    "                            continue\n"
    '                        _val = _o.get("value")\n'
    '                        _nm = _o.get("name")\n'
    "                        if _val and _nm and (_nm == label or label.startswith(f\"{_nm} (\")):\n"
    "                            return str(_val)\n"
    "                    break\n"
    "    return (await _opencode_model_catalog()).get(label, \"\")\n"
    "\n"
    "\n"
    "async def api_chat_slot_model(request: web.Request) -> web.Response:\n"
)

# ── 2: handler flow — resolve before storing slot.model ──
FLOW_OLD = (
    "    model_name = _normalize_model(body.get(\"model\", \"\"))\n"
    "    reason = _model_rejected_reason(model_name)\n"
    "    if reason:\n"
    '        logger.warning("Slot %s model rejected: %s", name, reason)\n'
    '        return web.json_response({"error": reason}, status=400)\n'
    "    if slot.model == model_name:\n"
    '        return web.json_response({"ok": True, "model": model_name})\n'
    "    session_key = _history_key_for(name)\n"
    "    provider = state.sessions.get_provider(session_key)\n"
    "    prior_model = slot.model\n"
    "    slot.model = model_name\n"
)
FLOW_NEW = (
    "    model_name = _normalize_model(body.get(\"model\", \"\"))\n"
    "    reason = _model_rejected_reason(model_name)\n"
    "    if reason:\n"
    '        logger.warning("Slot %s model rejected: %s", name, reason)\n'
    '        return web.json_response({"error": reason}, status=400)\n'
    "    session_key = _history_key_for(name)\n"
    "    provider = state.sessions.get_provider(session_key)\n"
    "    # opencode: the picker sends the DISPLAY label (\"Name (Provider)\")\n"
    "    # but the wire id is provider/model. Resolve labels (wire ids pass\n"
    "    # through) so slot.model and every downstream spawn/switch carry a\n"
    "    # value opencode accepts — a raw label would fail set_model and\n"
    "    # poison the next spawn.\n"
    '    if model_name and "/" not in model_name and model_name != "auto":\n'
    "        model_name = (await _resolve_wire_model_id(model_name, provider)) or model_name\n"
    "    if slot.model == model_name:\n"
    '        return web.json_response({"ok": True, "model": model_name})\n'
    "    prior_model = slot.model\n"
    "    slot.model = model_name\n"
)

failures = 0
text = HANDLERS.read_text()
for label, old, new in (
    ("helpers", HELPERS_OLD, HELPERS_NEW),
    ("flow", FLOW_OLD, FLOW_NEW),
):
    count = text.count(old)
    if count != 1:
        print(f"FAIL {label}: expected exactly 1 match, found {count}")
        failures += 1
    else:
        text = text.replace(old, new)
if not failures:
    backup = HANDLERS.with_suffix(HANDLERS.suffix + ".pkbak")
    if not backup.exists():
        backup.write_text(HANDLERS.read_text())
    HANDLERS.write_text(text)
    print("OK   chat_handlers.py")

sys.exit(1 if failures else 0)
