#!/usr/bin/env python3
"""Fix "model isn't offered right now" for opencode.

Root cause: the pick API stores opencode's provider/model WIRE id in
slot.model, but the frontend's "offered" list is label-keyed
(model_name, e.g. "DeepSeek V4 Flash (DeepSeek)") — wire ids never match,
so the dropdown always reports the pinned model as not offered.

Fix: slot.model stores the DISPLAY LABEL (frontend-native); every
set_model boundary resolves label -> wire id via configOptions.

Edits:
  1. acp/_dispatch.py      — add resolve_opencode_wire_id()
  2. acp/client.py         — import + resolve in AcpClient.set_model
  3. acp/session_handle.py — import + resolve in AcpSessionHandle.set_model (KAS)
  4. chat_handlers.py      — api_chat_slot_model stores the label, no overwrite
"""
import pathlib

PKG = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew"
)
DISPATCH = PKG / "acp/_dispatch.py"
CLIENT = PKG / "acp/client.py"
HANDLE = PKG / "acp/session_handle.py"
CHANDLERS = PKG / "dashboard/chat_handlers.py"

RESOLVER = '''


def resolve_opencode_wire_id(config_options: object, model_id: str) -> str:
    """Map a dashboard display label to opencode's ``provider/model`` wire id.

    The dashboard catalog labels models as ``"Name (Provider Display)"`` while
    opencode's configOptions model select names them ``"Provider Display/Name"``.
    Wire ids (contain ``/``) and the empty/``auto`` sentinels pass through; an
    unmappable label also passes through so the caller's own handling decides
    (``AcpModelUnavailable``, or a graceful backend default).

    Exact candidate match wins; a bare-name (name-part) match is the fallback
    so raw models.dev names (``"DeepSeek V4 Flash"``) still resolve.
    """
    if not model_id or model_id == "auto" or "/" in model_id:
        return model_id
    _label = model_id.strip()
    m = re.match(r"^(?P<name>.*) \\((?P<provider>[^()]*)\\)$", _label)
    candidate = f"{m.group('provider')}/{m.group('name')}" if m else ""
    if not isinstance(config_options, (list, tuple)):
        return model_id
    for opt in config_options:
        if not isinstance(opt, dict) or opt.get("id") != "model":
            continue
        _options = opt.get("options", []) or []
        for o in _options:
            if (
                isinstance(o, dict)
                and o.get("value")
                and candidate
                and str(o.get("name") or "") == candidate
            ):
                return str(o["value"])
        for o in _options:
            if not isinstance(o, dict) or not o.get("value"):
                continue
            if str(o.get("name") or "").split("/", 1)[-1] == _label:
                return str(o["value"])
        break
    return model_id
'''


def backup(path: pathlib.Path, suffix: str) -> None:
    b = path.with_suffix(path.suffix + suffix)
    if not b.exists():
        b.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def patch(path: pathlib.Path, old: str, new: str, label: str) -> None:
    t = path.read_text(encoding="utf-8")
    n = t.count(old)
    if n != 1:
        raise SystemExit(f"FAIL {label}: expected 1 match, found {n}")
    backup(path, ".modelbak")
    path.write_text(t.replace(old, new), encoding="utf-8")
    print(f"OK   {label}")


# 1. Resolver in _dispatch.py
if "def resolve_opencode_wire_id" not in DISPATCH.read_text(encoding="utf-8"):
    backup(DISPATCH, ".modelbak")
    DISPATCH.write_text(
        DISPATCH.read_text(encoding="utf-8") + RESOLVER, encoding="utf-8"
    )
    print("OK   _dispatch.py resolver added")
else:
    print("SKIP _dispatch.py (resolver present)")

# 2. AcpClient.set_model
patch(
    CLIENT,
    "from kiro_crew.acp._dispatch import (\n",
    "from kiro_crew.acp._dispatch import (\n"
    "    resolve_opencode_wire_id,\n",
    "client.py import",
)
patch(
    CLIENT,
    '        if not self._session_id:\n'
    '            raise AcpError("Cannot set model before session is initialized")\n',
    '        if not self._session_id:\n'
    '            raise AcpError("Cannot set model before session is initialized")\n'
    "        # opencode (kas): the dashboard stores display labels in slot.model;\n"
    "        # map to the provider/model wire id via this session's configOptions\n"
    "        # before the wire (wire ids pass through unchanged).\n"
    "        model_id = resolve_opencode_wire_id(self._config_options, model_id)\n",
    "client.py set_model",
)

# 3. AcpSessionHandle.set_model (KAS path)
patch(
    HANDLE,
    "from kiro_crew.acp._dispatch import (\n",
    "from kiro_crew.acp._dispatch import (\n"
    "    resolve_opencode_wire_id,\n",
    "session_handle.py import",
)
patch(
    HANDLE,
    '        if self._runtime.acp_backend == ACP_BACKEND_KAS:\n'
    '            # KAS implements no ``session/set_model``; the model is one of its\n',
    '        if self._runtime.acp_backend == ACP_BACKEND_KAS:\n'
    "            # opencode stores the dashboard display label in slot.model;\n"
    "            # map it to the provider/model wire id via this session's\n"
    "            # configOptions (wire ids pass through unchanged).\n"
    "            resolved = resolve_opencode_wire_id(self._config_options, resolved)\n"
    '            # KAS implements no ``session/set_model``; the model is one of its\n',
    "session_handle.py set_model",
)

# 4. api_chat_slot_model: store the label, resolve at set boundaries
patch(
    CHANDLERS,
    '    # opencode: the picker sends the DISPLAY label ("Name (Provider)")\n'
    "    # but the wire id is provider/model. Resolve labels (wire ids pass\n"
    "    # through) so slot.model and every downstream spawn/switch carry a\n"
    "    # value opencode accepts \u2014 a raw label would fail set_model and\n"
    "    # poison the next spawn.\n"
    '    if model_name and "/" not in model_name and model_name != "auto":\n'
    "        model_name = (await _resolve_wire_model_id(model_name, provider)) or model_name\n",
    "    # opencode: slot.model stores the DISPLAY LABEL the picker sent \u2014 the\n"
    "    # frontend's \"offered\" list is label-keyed (model_name), so a wire id\n"
    "    # here would render the pin \"not offered\". Every set_model boundary\n"
    "    # resolves label -> wire id via configOptions (resolve_opencode_wire_id).\n",
    "chat_handlers.py pick stores label",
)

print("ALL DONE")
