"""Shared free-text model switching for messaging channels.

Telegram has the full picker UI; every other channel gets the stateless
free-text path: ``/model <query>`` resolves against the opencode catalog
(``opencode models --verbose``) and applies the match to the conversation's
session. Multi-match queries list the candidates and ask for a narrower
query or a full id — no per-message picker state to expire.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time

from kiro_crew.acp.kas_assets import resolve_opencode_bin

logger = logging.getLogger(__name__)

_OPENCODE_MODELS_CACHE_TTL = 300.0
_MODEL_CACHE: tuple[list[tuple[str, str]], float] | None = None
_MAX_MATCHES_SHOWN = 10

_MODEL_CMD_RE = re.compile(r"^[/!]model(?:\s+(.*))?$", re.IGNORECASE)


def command_arg(text: str) -> str | None:
    """The argument of a ``/model ...`` / ``!model ...`` message, or None when
    *text* is not a model command. A bare command yields ``""``."""
    m = _MODEL_CMD_RE.match(text.strip())
    return (m.group(1) or "").strip() if m else None


async def fetch_opencode_model_rows() -> list[tuple[str, str]]:
    """``(model_id, display_label)`` rows from the opencode catalog (cached)."""
    global _MODEL_CACHE
    if (
        _MODEL_CACHE is not None
        and time.time() - _MODEL_CACHE[1] < _OPENCODE_MODELS_CACHE_TTL
    ):
        return _MODEL_CACHE[0]
    import subprocess

    rows: list[tuple[str, str]] = []
    try:
        from kiro_crew.sandbox import create_subprocess_limited

        proc = await create_subprocess_limited(
            resolve_opencode_bin() or "opencode",
            "models",
            "--verbose",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode == 0 and stdout.strip():
            buf = ""
            for line in stdout.decode(errors="replace").splitlines():
                if line.lstrip().startswith("{"):
                    buf = line
                    continue
                if buf:
                    buf += "\n" + line
                    try:
                        m = json.loads(buf)
                    except json.JSONDecodeError:
                        continue
                    buf = ""
                    if not isinstance(m, dict):
                        continue
                    mid, pid = m.get("id"), m.get("providerID")
                    if isinstance(mid, str) and isinstance(pid, str) and mid and pid:
                        rows.append((f"{pid}/{mid}", str(m.get("name") or mid)))
    except Exception:
        logger.warning("model pick: opencode catalog fetch failed", exc_info=True)
        return []
    _MODEL_CACHE = (rows, time.time())
    return rows


def resolve_model_query(
    rows: list[tuple[str, str]], query: str
) -> tuple[str, object]:
    """(kind, payload): ``("apply", id)`` | ``("pick", [matches])`` |
    ``("none", None)``."""
    ql = query.strip().lower()
    if not ql:
        return "none", None
    for mid, _label in rows:
        if mid.lower() == ql:
            return "apply", mid
    fuzzy = [r for r in rows if ql in r[0].lower() or ql in r[1].lower()]
    if not fuzzy:
        return "none", None
    if len(fuzzy) == 1:
        return "apply", fuzzy[0][0]
    return "pick", fuzzy


async def apply_model(sessions: object, session_key: str, model_id: str) -> str:
    """Switch *session_key* to *model_id*; returns the outcome line."""
    label = model_id or "Auto"
    if not model_id:
        return "✅ Model set to Auto — applies to your next message."
    if not sessions.has_session(session_key):
        return f"✅ Model set to `{label}` — applies to your next message."
    if not await sessions.try_acquire(session_key):
        return (
            f"✅ Model set to `{label}`, but a reply is still running — it "
            "applies to your next conversation."
        )
    try:
        provider = sessions.get_provider(session_key)
        set_model = getattr(getattr(provider, "client", None), "set_model", None)
        if set_model is None:
            return (
                f"✅ Model set to `{label}` — this conversation keeps its "
                "current model; applies to your next one."
            )
        await set_model(model_id)
        return f"✅ Model switched to `{label}`."
    except Exception as exc:  # noqa: BLE001 - user-facing best effort
        logger.warning("model pick: switch failed for %s: %s", session_key, exc)
        return (
            f"⚠️ Could not switch to `{label}` ({exc}) — it is recorded for "
            "your next conversation."
        )
    finally:
        try:
            sessions.release(session_key)
        except Exception:  # noqa: BLE001 - never mask the outcome
            pass


def render_matches(query: str, matches: list[tuple[str, str]]) -> str:
    """A stateless disambiguation list for multi-match queries."""
    lines = [
        f"`{query}` matched {len(matches)} models — send `/model` with a "
        "full id or a more specific name:"
    ]
    for mid, label in matches[:_MAX_MATCHES_SHOWN]:
        lines.append(f"- `{mid}` ({label})")
    if len(matches) > _MAX_MATCHES_SHOWN:
        lines.append(f"… and {len(matches) - _MAX_MATCHES_SHOWN} more")
    return "\n".join(lines)
