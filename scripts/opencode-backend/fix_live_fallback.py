#!/usr/bin/env python3
"""Let _context_snapshot_fields_inner fall through to the persisted snapshot
when the resident provider has no telemetry yet (resumed via session/load on
startup — no usage_update has fired). Before the resume fix this never
happened: a load failure meant no provider existed until the first turn."""
import pathlib
import sys

HANDLERS = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_handlers.py"
)

OLD = (
    "    provider = state.sessions.get_provider(effective_session_key(slot))\n"
    "    if provider is not None:\n"
    "        return _context_reading(\n"
    "            provider.context_usage_pct(),\n"
    "            (provider.context_used_tokens() if hasattr(provider, \"context_used_tokens\") else 0),\n"
    "            (provider.context_window_tokens() if hasattr(provider, \"context_window_tokens\") else 0),\n"
    "            stale=False,\n"
    "            cost=(provider.session_cost() if hasattr(provider, \"session_cost\") else None),\n"
    "        )\n"
)
NEW = (
    "    provider = state.sessions.get_provider(effective_session_key(slot))\n"
    "    if provider is not None:\n"
    "        live = _context_reading(\n"
    "            provider.context_usage_pct(),\n"
    "            (provider.context_used_tokens() if hasattr(provider, \"context_used_tokens\") else 0),\n"
    "            (provider.context_window_tokens() if hasattr(provider, \"context_window_tokens\") else 0),\n"
    "            stale=False,\n"
    "            cost=(provider.session_cost() if hasattr(provider, \"session_cost\") else None),\n"
    "        )\n"
    "        if live:\n"
    "            return live\n"
    "        # Resident but silent: resumed on load (session/load), so no\n"
    "        # usage_update has fired yet and the handle has no reading of its\n"
    "        # own. Fall through to the persisted snapshot — it describes the\n"
    "        # session up to its last turn, and this process's first turn\n"
    "        # overwrites it with measured truth.\n"
)

text = HANDLERS.read_text()
count = text.count(OLD)
if count != 1:
    print(f"FAIL: expected exactly 1 match, found {count}")
    sys.exit(1)
backup = HANDLERS.with_suffix(HANDLERS.suffix + ".livebak")
if not backup.exists():
    backup.write_text(text)
HANDLERS.write_text(text.replace(OLD, NEW))
print("OK chat_handlers.py")
