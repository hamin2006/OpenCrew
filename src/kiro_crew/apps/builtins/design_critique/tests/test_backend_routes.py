"""The backend mounts its three routes on the gateway aiohttp app."""

from __future__ import annotations

import asyncio
from pathlib import Path

from aiohttp import web

from kiro_crew.apps.builtins.design_critique import register_routes
from kiro_crew.apps.builtins.design_critique.backend import routes


def test_register_routes_mounts_the_three_endpoints() -> None:
    app = web.Application()
    register_routes(app)
    mounted = {
        (r.method, r.resource.canonical)
        for r in app.router.routes()
        if r.resource is not None
    }
    assert ("GET", "/api/apps/design-critique/method") in mounted
    assert ("POST", "/api/apps/design-critique/discover") in mounted
    assert ("POST", "/api/apps/design-critique/render") in mounted


def test_only_http_urls_are_renderable() -> None:
    assert routes._is_http_url("https://example.com")
    assert routes._is_http_url("http://localhost:3000")
    # A file:// URL would turn the renderer into a local-file read primitive.
    assert not routes._is_http_url("file:///etc/passwd")
    assert not routes._is_http_url("ftp://host/x")


def test_credential_dirs_are_refused() -> None:
    assert routes._is_sensitive_dir(Path.home() / ".ssh")


class _Req:
    """Minimal stand-in exposing the one method the handler awaits."""

    def __init__(self, payload: object) -> None:
        self._payload = payload

    async def json(self) -> object:
        return self._payload


def test_render_rejects_non_object_picks() -> None:
    # {"picks": [null]} must not reach .get() on a non-dict and 500.
    resp = asyncio.run(
        routes._handle_render(_Req({"kind": "local", "value": "/tmp", "picks": [None]}))  # type: ignore[arg-type]
    )
    assert resp.status == 400


def test_render_rejects_repo_handle_escape(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # A crafted "../.." handle must not let render escape the clones dir.
    monkeypatch.setattr(routes, "_node", lambda: "/usr/bin/node")
    resp = asyncio.run(
        routes._handle_render(
            _Req({"kind": "repo", "handle": "../../etc", "picks": [{"id": "a", "label": "A"}]})  # type: ignore[arg-type]
        )
    )
    assert resp.status == 400
    assert b"bad_handle" in resp.body


def test_url_target_allows_loopback_blocks_internal() -> None:
    # Loopback is the advertised localhost-preview target; internal ranges and the
    # cloud-metadata endpoint are blocked; public and file:// are handled too.
    assert routes._url_target_allowed("http://127.0.0.1:3000/")
    assert routes._url_target_allowed("https://93.184.216.34/")
    assert not routes._url_target_allowed("http://169.254.169.254/")
    assert not routes._url_target_allowed("http://10.0.0.5/")
    assert not routes._url_target_allowed("file:///etc/passwd")


def test_discover_repo_rejects_non_http_url() -> None:
    # The git remote-helper RCE vector (`ext::sh -c …`) is refused before git runs.
    resp = asyncio.run(
        routes._handle_discover(_Req({"kind": "repo", "value": "ext::sh -c id"}))  # type: ignore[arg-type]
    )
    assert resp.status == 200
    assert b"no-access" in resp.body
