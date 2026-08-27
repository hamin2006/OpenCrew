"""This-crew AgentCore identity — Settings → Security on THIS gateway.

Each crew's own dashboard shows and (when the home policy is writable)
configures ``capabilities.agentcore``. This is not a Remote Crew / launch
control: a hub launching another box is a different crew.

GET is display-only. PUT is the operator's out-of-band write of the
standalone ``security_policy.json`` home file (same trust model as
computer-use Settings: dashboard cookie, no app token). The agent tool
gate still cannot touch that path. A fleet env override or a signed
document is refused rather than rewritten.

The ceiling is boot-frozen. A write that changes posture returns
``restart_required: true``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from aiohttp import web

from kiro_crew.platform.context import current_context
from kiro_crew.platform.governance import (
    PlatformCompositionError,
    _policy_home_path,
    agentcore_posture,
    parse_policy,
)
from kiro_crew.platform_compat import restrict_to_owner

logger = logging.getLogger(__name__)

OP_GET = "agentcore.identity.get"
OP_SAVE = "agentcore.identity.save"
_ENV_WORKLOAD = "KIROCREW_AGENTCORE_WORKLOAD_NAME"
_POSTURES = frozenset({"none", "workload", "login"})
_MINIMAL_BOOT = {
    "require_sandbox": True,
    "allow_terminal": False,
    "fail_closed": True,
}


def _audit(
    request: web.Request,
    *,
    operation: str,
    outcome: str,
    resources: str = "",
    error: str = "",
) -> None:
    try:
        import kiro_crew.dashboard.handlers as pkg

        pkg.sel().log_api_access(
            caller=request.get("user", "dashboard"),
            operation=operation,
            outcome=outcome,
            source="dashboard",
            resources=resources,
            error=error,
        )
    except Exception:
        logger.warning("SEL logging failed for %s", operation, exc_info=True)


def _workload_name() -> str:
    return os.environ.get(_ENV_WORKLOAD, "").strip()


def _file_posture() -> str | None:
    """Posture authored in the standalone home file, if any.

    Peek only — do not parse_policy. GET must still render when the
    running ceiling is stale (boot-frozen) or the file is not yet loaded.
    """
    path = _policy_home_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    caps = data.get("capabilities")
    if not isinstance(caps, dict):
        return None
    row = caps.get("agentcore")
    if not isinstance(row, dict) or not row.get("enabled"):
        return None
    posture = str(row.get("posture") or "").strip().lower()
    return posture if posture in {"workload", "login"} else None


def _write_reason() -> str:
    if os.environ.get("KIROCREW_SECURITY_POLICY", "").strip():
        return "fleet_override"
    path = _policy_home_path()
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unreadable"
    if not isinstance(data, dict):
        return "unreadable"
    identity = data.get("identity")
    if isinstance(identity, dict) and str(identity.get("signature") or "").strip():
        return "signed"
    return ""


def _snapshot() -> dict[str, Any]:
    """Display the authored posture; flag when the running ceiling is stale.

    Settings configures THIS crew's home policy. The ceiling is boot-frozen,
    so a file that disagrees with ``agentcore_posture(ceiling)`` is a pending
    restart, not an unset identity.
    """
    ceiling = getattr(current_context(), "governance", None)
    running = agentcore_posture(ceiling)
    reason = _write_reason()
    name = _workload_name()
    if reason == "fleet_override":
        displayed = running
        source = "policy" if running else ("env" if name else "unset")
        restart = False
    else:
        authored = _file_posture()
        displayed = authored if authored is not None else running
        if authored is not None:
            source = "policy"
        elif running is not None:
            source = "policy"
        elif name:
            source = "env"
        else:
            source = "unset"
        restart = authored is not None and authored != running
    return {
        "configured": displayed is not None,
        "posture": displayed,
        "workload_name": name,
        "source": source,
        "writable": reason == "",
        "write_blocked": reason or None,
        "restart_required": restart,
    }


def _read_home_document() -> dict[str, Any]:
    path = _policy_home_path()
    if not path.is_file():
        return {"version": 1, "boot": dict(_MINIMAL_BOOT), "capabilities": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlatformCompositionError(f"security policy is unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise PlatformCompositionError("security policy top level is not an object")
    return data


def _write_home_document(data: dict[str, Any]) -> None:
    parse_policy(data)
    path = _policy_home_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=False) + "\n"
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    restrict_to_owner(tmp)
    tmp.replace(path)


def _apply_posture(data: dict[str, Any], posture: str) -> dict[str, Any]:
    caps = data.get("capabilities")
    if not isinstance(caps, dict):
        caps = {}
        data["capabilities"] = caps
    if posture == "none":
        if "agentcore" in caps:
            caps["agentcore"] = {"enabled": False}
        return data
    caps["agentcore"] = {"enabled": True, "posture": posture}
    if "boot" not in data or not isinstance(data.get("boot"), dict):
        data["boot"] = dict(_MINIMAL_BOOT)
    if data.get("version") != 1:
        data["version"] = 1
    return data


async def api_agentcore_identity_get(request: web.Request) -> web.Response:
    """GET /api/agentcore/identity — this crew's AgentCore identity (read)."""
    try:
        payload = _snapshot()
    except Exception:
        logger.warning("agentcore identity snapshot failed", exc_info=True)
        _audit(request, operation=OP_GET, outcome="error", error="snapshot_failed")
        return web.json_response(
            {
                "configured": False,
                "posture": None,
                "workload_name": _workload_name(),
                "source": "unset",
                "writable": False,
                "write_blocked": "unavailable",
                "restart_required": False,
            }
        )
    _audit(request, operation=OP_GET, outcome="success")
    return web.json_response(payload)


async def api_agentcore_identity_save(request: web.Request) -> web.Response:
    """PUT /api/agentcore/identity — set this crew's AgentCore posture.

    Dashboard-browser callers only. App tokens are refused before the body
    is read: this writes the keystone the agent cannot touch.
    """
    if request.get("app"):
        _audit(
            request,
            operation=OP_SAVE,
            outcome="denied",
            error="app tokens may not write capabilities.agentcore",
        )
        return web.json_response(
            {"error": "dashboard user required", "code": "dashboard_user_required"},
            status=403,
        )
    try:
        body = await request.json()
    except Exception:
        _audit(request, operation=OP_SAVE, outcome="denied", resources="invalid_json")
        return web.json_response({"error": "invalid JSON", "code": "invalid_json"}, status=400)
    if not isinstance(body, dict):
        _audit(request, operation=OP_SAVE, outcome="denied", resources="body_not_object")
        return web.json_response(
            {"error": "request body must be a JSON object", "code": "invalid_json"},
            status=400,
        )
    raw = body.get("posture")
    if not isinstance(raw, str) or raw.strip().lower() not in _POSTURES:
        _audit(request, operation=OP_SAVE, outcome="denied", resources="bad_posture")
        return web.json_response(
            {
                "error": "posture must be none, workload, or login",
                "code": "invalid_agentcore_posture",
            },
            status=400,
        )
    posture = raw.strip().lower()
    blocked = _write_reason()
    if blocked:
        _audit(
            request,
            operation=OP_SAVE,
            outcome="denied",
            resources=blocked,
            error="policy not writable from this gateway",
        )
        return web.json_response(
            {
                "error": "this crew's security policy cannot be edited here",
                "code": "policy_not_writable",
                "write_blocked": blocked,
            },
            status=409,
        )
    try:
        path = _policy_home_path()
        if posture == "none" and not path.is_file():
            payload = _snapshot()
            _audit(request, operation=OP_SAVE, outcome="success", resources="none")
            return web.json_response(payload)
        data = _read_home_document()
        _apply_posture(data, posture)
        _write_home_document(data)
    except PlatformCompositionError as exc:
        _audit(request, operation=OP_SAVE, outcome="denied", error=str(exc))
        return web.json_response({"error": str(exc), "code": "invalid_policy"}, status=400)
    except OSError as exc:
        logger.warning("agentcore identity write failed", exc_info=True)
        _audit(request, operation=OP_SAVE, outcome="error", error=str(exc))
        return web.json_response(
            {"error": "could not write security policy", "code": "write_failed"},
            status=500,
        )
    payload = _snapshot()
    _audit(request, operation=OP_SAVE, outcome="success", resources=posture)
    return web.json_response(payload)
