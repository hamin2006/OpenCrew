"""Design Critique — backend API routes.

Registered at gateway startup by the ``BUILTIN_NAMES`` loop in
``dashboard/routes/system.py`` (via the package re-export in
``design_critique/__init__.py``).

These endpoints do every step that needs a shell or the filesystem — cloning a
repo, discovering its routes, and rendering screens to PNGs — server-side, so the
LLM agent never has to. The agent is then only ever asked to reason over finished
images with no tools, which is why it can no longer stall on a tool-approval
prompt that the app panel has nowhere to show.

Routes (browser-facing, same-origin authed):

  GET  /api/apps/design-critique/method    -> the critique method text to inline
  POST /api/apps/design-critique/discover  -> {kind,value} -> candidate screens
  POST /api/apps/design-critique/render     -> {kind,value,handle,picks} -> PNGs
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import re
import shutil
import socket
import time
import uuid
from functools import wraps
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from aiohttp import web

import kiro_crew
from kiro_crew.apps.manager import is_app_enabled
from kiro_crew.config.paths import config_dir
from kiro_crew.security import is_sensitive_path, path_contains_sensitive

logger = logging.getLogger(__name__)

APP_NAME = "design-critique"
_PREFIX = f"/api/apps/{APP_NAME}"

# Resolved from the installed package, in-process — never via a `python3 -c
# "import kiro_crew"` SHELL command, which the gateway's own security filter
# hard-blocks because the string contains the package name.
_SKILL_DIR = (
    Path(kiro_crew.__file__).parent
    / "apps/builtins/design_critique/skills/design-critique"
)
_SCRIPTS_DIR = _SKILL_DIR / "scripts"

# A route path or discovery id can be anything; collapse to a safe filename stem.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")

# First render on a machine without Google Chrome downloads a Chromium build
# (once, into a home cache). macOS dashboard users have Chrome, so the scripts'
# channel:'chrome' path skips the download — but keep the ceiling high enough
# that a cold first run still completes rather than being killed mid-download.
_DISCOVER_TIMEOUT = 180
_CAPTURE_TIMEOUT = 900
_CLONE_TIMEOUT = 180
# Clone dirs are reused between discover and render, then swept when stale.
_CLONE_TTL_SEC = 60 * 60


def _uploads_dir() -> Path:
    # Read at call time, not import: KIROCREW_HOME can relocate the data home and
    # a dev instance does exactly that.
    d = config_dir() / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _clones_dir() -> Path:
    d = _uploads_dir() / "dc-clones"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sweep_clones() -> None:
    # A clone lives only long enough to render from; drop anything past the TTL so
    # abandoned scans do not accumulate whole repositories under uploads.
    now = time.time()
    root = _clones_dir()
    for child in root.iterdir() if root.exists() else []:
        try:
            if child.is_dir() and now - child.stat().st_mtime > _CLONE_TTL_SEC:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            continue


def _node() -> str | None:
    return shutil.which("node")


def _is_sensitive_dir(p: Path) -> bool:
    # A local target must never let the renderer walk a credential directory
    # (~/.ssh, ~/.aws, keystore paths). Same screen the dashboard uses.
    s = str(p)
    return is_sensitive_path(s) or path_contains_sensitive(s)


def _is_http_url(u: str) -> bool:
    # Only http(s) may be rendered — a file:// or other scheme would turn the
    # renderer into a server-side read primitive for local files.
    return urlparse(u).scheme in ("http", "https")


def _url_target_allowed(u: str) -> bool:
    # SSRF guard for URL discovery/render. The feature intentionally supports a
    # localhost preview, so LOOPBACK is allowed; everything else internal is not
    # — link-local (incl. the 169.254.169.254 cloud-metadata endpoint), private
    # ranges, reserved, multicast, unspecified. Public hosts are allowed.
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    try:
        port = p.port or (443 if p.scheme == "https" else 80)
        infos = socket.getaddrinfo(p.hostname, port, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if ip.is_loopback:
            continue
        if (
            ip.is_private or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified
        ):
            return False
    return True


def _bad_request(error: str, code: str) -> web.Response:
    return web.json_response({"error": error, "code": code}, status=400)


def _require_enabled(handler):
    @wraps(handler)
    async def _wrapped(request: web.Request) -> web.Response:
        if not await asyncio.to_thread(is_app_enabled, APP_NAME):
            return web.json_response(
                {"error": f"{APP_NAME} is disabled", "code": "app_disabled"},
                status=403,
            )
        return await handler(request)

    return _wrapped


async def _json_object(
    request: web.Request,
) -> tuple[dict[str, Any] | None, web.Response | None]:
    try:
        body = await request.json()
    except ValueError:
        return None, _bad_request("invalid JSON", "invalid_json")
    if not isinstance(body, dict):
        return None, _bad_request("body must be a JSON object", "body_not_object")
    return body, None


async def _run(
    cmd: list[str], timeout: int, env: dict[str, str] | None = None
) -> tuple[int, str, str]:
    """Run a subprocess off the event loop, killing it if it overruns."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        # A timeout OR a cancelled request (the browser navigated away mid-scan)
        # must not leave the git/Playwright child running server-side.
        proc.kill()
        await proc.wait()
        raise
    return (
        proc.returncode or 0,
        out.decode("utf-8", "replace"),
        err.decode("utf-8", "replace"),
    )


def _script_env() -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"  # a private/bad repo must fail, never prompt
    return env


def _slug(text: str) -> str:
    s = _UNSAFE.sub("-", (text or "").strip("/")).strip("-")
    return s or "screen"


def _route_segments(path: str) -> list[str]:
    # Route paths are POSIX-style URLs, so parse them as URLs (portable), not with
    # a literal "/" split. Drops the leading "/", params (:id) and wildcards (*).
    return [
        p for p in PurePosixPath(path or "").parts
        if p not in ("", "/") and not p.startswith(":") and p != "*"
    ]


def _label_for(path: str) -> str:
    # A route becomes a one/two-word label the picker can show; "/" is the home.
    if not path or path == "/":
        return "Home"
    seg = _route_segments(path)
    return (seg[-1] if seg else "Home").replace("-", " ").replace("_", " ")[:18].strip() or "Home"


def _group_for(path: str) -> str:
    seg = _route_segments(path)
    return seg[0] if seg else "root"


# ── GET /method ──


async def _handle_method(request: web.Request) -> web.Response:
    # The critique voice and rubric used to be fetched by the agent with fs_read
    # (a tool call that stalls in the panel). Serve the same two files here so the
    # frontend can inline them into the tool-free prompt instead.
    def _read() -> dict[str, str]:
        skill = (_SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        checklist = (_SKILL_DIR / "frameworks/main-checklist.md").read_text(
            encoding="utf-8"
        )
        return {"skill": skill, "checklist": checklist}

    try:
        payload = await asyncio.to_thread(_read)
    except OSError as exc:
        logger.warning("design-critique: method files unreadable: %s", exc)
        return web.json_response(
            {"error": "method files not found", "code": "method_missing"}, status=500
        )
    return web.json_response(payload)


# ── POST /discover ──


async def _discover_from_dir(directory: Path, handle: str) -> dict[str, Any]:
    """Run discover-routes + a capture probe against a local/cloned directory."""
    node = _node()
    if node is None:
        return {
            "framework": "",
            "note": "",
            "blocked": {"reason": "other", "detail": "node is not installed on this machine, so screens cannot be discovered."},
            "screens": [],
            "flows": [],
            "cannotSee": [],
            "handle": handle,
        }

    rc, out, err = await _run(
        [node, str(_SCRIPTS_DIR / "discover-routes.mjs"), str(directory)],
        _DISCOVER_TIMEOUT,
        env=_script_env(),
    )
    try:
        disc = json.loads(out)
    except ValueError:
        logger.warning("design-critique discover-routes bad JSON: %s", err[:300])
        disc = {"framework": "", "routing": "none", "routes": [], "notes": []}

    routes = disc.get("routes") or []
    # Probe which routes actually render, so canSee is grounded rather than guessed.
    seeable: dict[str, bool] = {}
    cannot_see: list[str] = []
    if routes:
        csv = ",".join(str(r.get("path", "")) for r in routes[:20] if r.get("path"))
        prc, pout, perr = await _run(
            [
                node,
                str(_SCRIPTS_DIR / "capture-build.mjs"),
                str(directory),
                f"--routes={csv}",
                f"--out={_uploads_dir()}",
            ],
            _CAPTURE_TIMEOUT,
            env=_script_env(),
        )
        try:
            probe = json.loads(pout)
        except ValueError:
            probe = {}
        for s in probe.get("screens") or []:
            seeable[str(s.get("route"))] = True
        if probe.get("blockedBy"):
            b = probe["blockedBy"]
            cannot_see.append(
                f"{b.get('onScreens', '')} of {b.get('ofScreens', '')} screens blocked by a {b.get('likely', 'gate')}."
            )
        if probe.get("buildDir") is None and probe.get("notes"):
            cannot_see.extend(str(n) for n in probe["notes"])

    screens = []
    for r in routes:
        path = str(r.get("path", ""))
        if not path:
            continue
        # Default False: a route the probe returned no image for is not renderable
        # (marking it renderable walks the user into a render that always fails).
        can = seeable.get(path, False)
        screens.append(
            {
                "id": _slug(path),
                "label": _label_for(path),
                "ref": path,
                "group": _group_for(path),
                "canSee": bool(can),
                "why": "" if can else "needs a build or a running server to render",
            }
        )

    # Loose flows by top-level group, marked a guess since no navigation was seen.
    flows = []
    by_group: dict[str, list[str]] = {}
    for s in screens:
        by_group.setdefault(s["group"], []).append(s["id"])
    for group, ids in by_group.items():
        if len(ids) > 1:
            flows.append(
                {
                    "label": group,
                    "why": "grouped by shared top-level path",
                    "basis": "guess",
                    "screenIds": ids,
                }
            )

    return {
        "framework": disc.get("framework", ""),
        "note": (disc.get("notes") or [""])[0] if disc.get("notes") else "",
        "blocked": None,
        "screens": screens,
        "flows": flows,
        "cannotSee": cannot_see,
        "handle": handle,
    }


async def _handle_discover(request: web.Request) -> web.Response:
    body, err = await _json_object(request)
    if body is None:
        return err or _bad_request("invalid JSON", "invalid_json")
    kind = str(body.get("kind") or "").strip()
    value = str(body.get("value") or "").strip()
    if not kind or not value:
        return _bad_request("kind and value are required", "missing_field")

    await asyncio.to_thread(_sweep_clones)

    if kind == "figma":
        # Exporting Figma frames needs the Figma desktop tools, which only exist
        # inside an agent — and an agent in an app panel is exactly what stalls.
        # Route the user to frame-image export, which runs the working image path.
        return web.json_response(
            {
                "framework": "Figma",
                "note": "",
                "blocked": {
                    "reason": "figma-export-needed",
                    "detail": "Export the frames you want critiqued as PNGs and drop them in as screenshots — that runs the same critique without needing the Figma desktop app.",
                },
                "screens": [],
                "flows": [],
                "cannotSee": [],
                "handle": "",
            }
        )

    if kind == "repo":
        if not _is_http_url(value):
            # Only http(s) repository URLs. Rejects the git remote-helper RCE
            # (`ext::sh -c …`), file://, git://, ssh://, and option injection
            # (a value like `--upload-pack=…`) before git ever sees the value.
            return web.json_response(
                {
                    "framework": "",
                    "note": "",
                    "blocked": {"reason": "no-access", "detail": "only http(s) repository URLs are supported."},
                    "screens": [],
                    "flows": [],
                    "cannotSee": [],
                    "handle": "",
                }
            )
        clone_id = uuid.uuid4().hex[:12]
        target = _clones_dir() / clone_id
        rc, out, cerr = await _run(
            # Pin remote-helper transports off and pass the URL after `--` so a
            # crafted value can neither run a helper nor be read as an option.
            [
                "git",
                "-c", "protocol.ext.allow=never",
                "-c", "protocol.allow=user",
                "clone", "--depth", "1", "--", value, str(target),
            ],
            _CLONE_TIMEOUT,
            env=_script_env(),
        )
        if rc != 0 or not target.exists():
            # GitHub says "Repository not found" for both a missing repo and a
            # private one you cannot read; do not guess which.
            return web.json_response(
                {
                    "framework": "",
                    "note": "",
                    "blocked": {
                        "reason": "no-access",
                        "detail": (cerr or "git clone failed").strip()[:500]
                        + " (the repository may not exist, or it is private and cannot be read).",
                    },
                    "screens": [],
                    "flows": [],
                    "cannotSee": [],
                    "handle": "",
                }
            )
        result = await _discover_from_dir(target, handle=clone_id)
        return web.json_response(result)

    if kind == "local":
        p = Path(value).expanduser()
        if _is_sensitive_dir(p):
            return web.json_response(
                {
                    "framework": "",
                    "note": "",
                    "blocked": {"reason": "other", "detail": "that path is protected and can't be read."},
                    "screens": [],
                    "flows": [],
                    "cannotSee": [],
                    "handle": "",
                }
            )
        if not p.exists():
            return web.json_response(
                {
                    "framework": "",
                    "note": "",
                    "blocked": {"reason": "not-found", "detail": f"no such path: {value}"},
                    "screens": [],
                    "flows": [],
                    "cannotSee": [],
                    "handle": "",
                }
            )
        # A local checkout is used in place; its path IS the render handle.
        result = await _discover_from_dir(p, handle=f"local:{p}")
        return web.json_response(result)

    if kind == "url":
        if not _url_target_allowed(value):
            return web.json_response(
                {
                    "framework": "",
                    "note": "",
                    "blocked": {"reason": "other", "detail": "that URL can't be reviewed — use an http(s) address that isn't an internal/private host."},
                    "screens": [],
                    "flows": [],
                    "cannotSee": [],
                    "handle": "",
                }
            )
        # A served URL: treat the page itself as one screen. Link-crawling is left
        # out on purpose — the user can add more screenshots after the first read.
        return web.json_response(
            {
                "framework": "live site",
                "note": "one page discovered; add more screenshots to widen the review",
                "blocked": None,
                "screens": [
                    {
                        "id": "page",
                        "label": "Page",
                        "ref": value,
                        "group": "site",
                        "canSee": True,
                        "why": "",
                    }
                ],
                "flows": [],
                "cannotSee": [],
                "handle": f"url:{value}",
            }
        )

    return _bad_request(f"unknown kind: {kind}", "bad_kind")


# ── POST /render ──


async def _handle_render(request: web.Request) -> web.Response:
    body, err = await _json_object(request)
    if body is None:
        return err or _bad_request("invalid JSON", "invalid_json")
    kind = str(body.get("kind") or "").strip()
    value = str(body.get("value") or "").strip()
    handle = str(body.get("handle") or "").strip()
    picks = body.get("picks")
    if not isinstance(picks, list) or not picks:
        return _bad_request("picks must be a non-empty array", "missing_picks")
    if not all(isinstance(p, dict) for p in picks):
        return _bad_request("each pick must be an object", "bad_pick")

    node = _node()
    if node is None:
        return _bad_request("node is not installed on this machine", "node_missing")

    refs = [str(p.get("ref") or p.get("id") or "") for p in picks]
    labels = [str(p.get("label") or "").strip() or _label_for(refs[i]) for i, p in enumerate(picks)]

    screens: list[dict[str, Any]] = []
    could_not_see: list[str] = []

    if kind in ("repo", "local"):
        if kind == "repo":
            # `handle` comes from the client; a crafted "../.." must not let the
            # render escape the clones dir. Resolve and require containment.
            clones = _clones_dir().resolve()
            directory = (clones / handle).resolve()
            if not directory.is_relative_to(clones):
                return _bad_request("invalid clone handle", "bad_handle")
        else:
            directory = Path(handle[len("local:"):] if handle.startswith("local:") else value).expanduser()
            if _is_sensitive_dir(directory):
                return _bad_request("that path is protected and can't be read.", "protected_path")
        if not directory.exists():
            return _bad_request(
                "the discovered project is no longer available; run discovery again",
                "handle_expired",
            )
        csv = ",".join(r for r in refs if r)
        rc, out, cerr = await _run(
            [
                node,
                str(_SCRIPTS_DIR / "capture-build.mjs"),
                str(directory),
                f"--routes={csv}",
                f"--out={_uploads_dir()}",
                "--full",
            ],
            _CAPTURE_TIMEOUT,
            env=_script_env(),
        )
        try:
            cap = json.loads(out)
        except ValueError:
            return _bad_request("could not render the selected screens", "render_failed")
        by_route = {str(s.get("route")): s for s in (cap.get("screens") or [])}
        for i, ref in enumerate(refs):
            s = by_route.get(ref)
            if s and s.get("path"):
                screens.append({"step": i + 1, "label": labels[i], "path": s["path"]})
            else:
                could_not_see.append(labels[i])
        if cap.get("blockedBy"):
            could_not_see.append("a login or consent gate blocked some screens")

    elif kind == "url":
        base = value or (handle[len("url:"):] if handle.startswith("url:") else "")
        routes = [r for r in refs if r]
        # capture-site wants same-origin route paths under one base; if a pick is a
        # full URL use it as the base with a single "/" route.
        if len(routes) == 1 and routes[0].startswith("http"):
            base, routes = routes[0], ["/"]
        if not _url_target_allowed(base):
            return _bad_request("that URL can't be rendered (internal/private hosts are blocked)", "bad_url")
        rc, out, cerr = await _run(
            [
                node,
                str(_SCRIPTS_DIR / "capture-site.mjs"),
                f"--base={base}",
                f"--routes={','.join(routes) or '/'}",
                f"--out={_uploads_dir()}",
                "--full",
            ],
            _CAPTURE_TIMEOUT,
            env=_script_env(),
        )
        step = 0
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            step += 1
            if rec.get("ok") and rec.get("file"):
                screens.append(
                    {"step": step, "label": labels[min(step - 1, len(labels) - 1)], "path": rec["file"]}
                )
            else:
                could_not_see.append(str(rec.get("label") or rec.get("route") or "a page"))
    else:
        return _bad_request(f"cannot render kind: {kind}", "bad_kind")

    return web.json_response({"screens": screens, "couldNotSee": could_not_see})


# ── Registration ──


def register_routes(app: web.Application) -> None:
    """Register Design Critique routes on the gateway's aiohttp Application."""
    app.router.add_get(f"{_PREFIX}/method", _require_enabled(_handle_method))
    app.router.add_post(f"{_PREFIX}/discover", _require_enabled(_handle_discover))
    app.router.add_post(f"{_PREFIX}/render", _require_enabled(_handle_render))
