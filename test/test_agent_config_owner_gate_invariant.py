"""Every mutating route registered by the agent_config registrar refuses non-owner callers.

Unlike ``test_agents_endpoints_owner_auth.py`` which filters by handler module
(``handlers.agents``), this test walks ALL mutating routes registered by both
the ``agent_config`` and ``agents`` route registrars without filtering by
handler module. This ensures that new routes added to ANY handler module in the
registrar cannot silently escape the owner gate invariant.

A mutating route (POST/PUT/PATCH/DELETE) that is registered through the
registrar must either:
1. Return 403 with ``code: owner_only`` for a non-owner caller, OR
2. Be explicitly documented in the ``_PRE_OWNER_EXCLUSIONS`` set below with a
   justification for why the route intentionally skips the owner gate.

The coherence floor ``_MINIMUM_MUTATING_ROUTES`` prevents the walk from going
vacuous if a refactor empties the route table.
"""

from __future__ import annotations

import re

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from kiro_crew.dashboard.routes import agent_config as agent_config_routes
from kiro_crew.dashboard.routes import agents as agents_routes

pytestmark = pytest.mark.asyncio

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# --------------------------------------------------------------------------- #
# Pre-owner exclusions: routes that intentionally only require authentication
# (not ownership) because they execute during the initial onboarding flow
# BEFORE an owner is configured.
# --------------------------------------------------------------------------- #
_PRE_OWNER_EXCLUSIONS: frozenset[tuple[str, str]] = frozenset(
    {
        # Onboarding import routes use ``_caller()`` which checks authentication
        # but not ownership. These routes run during initial setup when the user
        # is importing configuration from another installation -- there is no
        # configured owner yet, so the owner gate cannot apply.
        ("POST", "/api/onboarding/import/apply"),
        ("PUT", "/api/onboarding/import/state"),
    }
)

# --------------------------------------------------------------------------- #
# Coherence floor: the walk must find at least this many mutating routes.
# If a refactor removes or relocates routes such that the walk finds fewer
# than this threshold, the test fails loudly rather than passing vacuously.
# --------------------------------------------------------------------------- #
_MINIMUM_MUTATING_ROUTES = 20


class _FakeState:
    """Simulates a state object with no configured owner.

    When ``owner_id`` is empty the ``is_owner_dashboard_request`` predicate
    rejects all callers that are not the signed local bootstrap subject.
    """

    owner_id = ""


def _build_app() -> web.Application:
    """Build a minimal app with both route registrars and identity middleware."""

    @web.middleware
    async def _identity(request, handler):
        # Stand-in for the token-auth middleware: populates the AUTHENTICATED
        # claims that the owner predicate reads. Tests select the caller via
        # headers so we can simulate a non-owner caller.
        request["user"] = request.headers.get("X-Test-User", "local-app")
        request["app"] = request.headers.get("X-Test-App", "")
        return await handler(request)

    app = web.Application(middlewares=[_identity])
    app["state"] = _FakeState()
    # Register BOTH registrars so the walk covers the full route surface.
    agents_routes.register(app)
    agent_config_routes.register(app)
    return app


def _all_mutating_routes(app: web.Application) -> set[tuple[str, str]]:
    """Enumerate every mutating route from the app router.

    Does NOT filter by handler module -- walks all routes regardless of which
    handler module they resolve to. This is the key difference from the
    per-module test in ``test_agents_endpoints_owner_auth.py``.
    """
    found: set[tuple[str, str]] = set()
    for route in app.router.routes():
        if route.method not in _MUTATING_METHODS:
            continue
        resource = route.resource
        if resource is None:
            continue
        canonical = resource.canonical
        # Skip routes that are in the pre-owner exclusion set.
        if (route.method, canonical) in _PRE_OWNER_EXCLUSIONS:
            continue
        found.add((route.method, canonical))
    return found


def _substitute_path_params(canonical: str) -> str:
    """Replace ``{param}`` placeholders with a dummy value for requests."""
    return re.sub(r"\{[^}]+\}", "test-item", canonical)


async def test_walk_finds_minimum_mutating_routes() -> None:
    """The enumeration finds at least the coherence floor of mutating routes.

    Guards against the walk going vacuous if a refactor moves or removes route
    registrations.
    """
    app = _build_app()
    found = _all_mutating_routes(app)
    assert len(found) >= _MINIMUM_MUTATING_ROUTES, (
        f"Route walk found only {len(found)} mutating routes "
        f"(expected >= {_MINIMUM_MUTATING_ROUTES}). "
        f"If routes were intentionally removed, lower the floor. "
        f"Found: {sorted(found)}"
    )


async def test_every_mutating_route_refuses_non_owner() -> None:
    """A non-owner dashboard subject gets 403 on every mutating route.

    The request carries no JSON body and uses a non-owner identity header.
    The owner gate must fire BEFORE body parsing or state access, so the 403
    should always come first (handlers that fail with 500 due to missing state
    objects would indicate a broken test setup, not a missing gate).
    """
    app = _build_app()
    routes = _all_mutating_routes(app)
    assert routes, "no mutating routes found -- test setup is broken"

    async with TestClient(TestServer(app)) as client:
        for method, canonical in sorted(routes):
            path = _substitute_path_params(canonical)
            resp = await client.request(
                method, path, headers={"X-Test-User": "someone-else"}
            )
            assert resp.status == 403, (
                f"{method} {canonical} answered {resp.status} for a non-owner "
                f"subject -- every mutating route must be owner-gated "
                f"(or explicitly listed in _PRE_OWNER_EXCLUSIONS)"
            )
            body = await resp.json()
            assert body.get("code") == "owner_only", (
                f"{method} {canonical} returned 403 but with unexpected code "
                f"{body.get('code')!r} -- expected 'owner_only'"
            )


async def test_pre_owner_exclusions_are_actually_registered() -> None:
    """Every route in the exclusion set must actually exist in the router.

    Prevents stale exclusions from hiding the removal of a once-excluded route.
    """
    app = _build_app()
    all_routes: set[tuple[str, str]] = set()
    for route in app.router.routes():
        resource = route.resource
        if resource is None:
            continue
        all_routes.add((route.method, resource.canonical))

    for method, path in _PRE_OWNER_EXCLUSIONS:
        assert (method, path) in all_routes, (
            f"Excluded route {method} {path} is not registered in the router. "
            f"Remove it from _PRE_OWNER_EXCLUSIONS or fix the route registration."
        )
