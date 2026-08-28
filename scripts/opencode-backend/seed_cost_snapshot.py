#!/usr/bin/env python3
"""Seed session_cost into the persisted context snapshot so the Spent row
shows on page load (cold path) without requiring a chat turn.

Patch 1 (state.py):        broadcast_context_usage persists cost alongside pct/tokens.
Patch 2 (chat_handlers.py): cold snapshot read forwards cost to _context_reading.
"""
import pathlib
import sys

WHEEL = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew"
)
STATE = WHEEL / "dashboard/state.py"
HANDLERS = WHEEL / "dashboard/chat_handlers.py"

EDITS = [
    (
        STATE,
        "        snapshot: dict[str, Any] = {\"pct\": pct, \"model\": slot.model}\n"
        "        window = payload.get(\"window_tokens\") or 0\n"
        "        if window:\n"
        "            snapshot[\"window_tokens\"] = window\n"
        "            snapshot[\"used_tokens\"] = payload.get(\"used_tokens\", 0)\n"
        "        with self._context_snapshots_lock:\n",
        "        snapshot: dict[str, Any] = {\"pct\": pct, \"model\": slot.model}\n"
        "        window = payload.get(\"window_tokens\") or 0\n"
        "        if window:\n"
        "            snapshot[\"window_tokens\"] = window\n"
        "            snapshot[\"used_tokens\"] = payload.get(\"used_tokens\", 0)\n"
        "        # Cost is mirrored too so the cold-read path (gateway restart,\n"
        "        # expired ACP process) can show Spent on page load without a\n"
        "        # turn — same survival contract as pct. `_context_reading`\n"
        "        # filters non-finite values, so store what the frame carried.\n"
        "        cost = payload.get(\"cost\")\n"
        "        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost > 0:\n"
        "            snapshot[\"cost\"] = round(cost, 4)\n"
        "        with self._context_snapshots_lock:\n",
    ),
    (
        STATE,
        "``payload`` is the frame as broadcast (``{slot, pct, used_tokens?,\n"
        "        window_tokens?, reset?}``).",
        "``payload`` is the frame as broadcast (``{slot, pct, used_tokens?,\n"
        "        window_tokens?, cost?, reset?}``).",
    ),
    (
        HANDLERS,
        "    return _context_reading(\n"
        "        snapshot.get(\"pct\"),\n"
        "        snapshot.get(\"used_tokens\"),\n"
        "        snapshot.get(\"window_tokens\"),\n"
        "        stale=True,\n"
        "    )\n",
        "    return _context_reading(\n"
        "        snapshot.get(\"pct\"),\n"
        "        snapshot.get(\"used_tokens\"),\n"
        "        snapshot.get(\"window_tokens\"),\n"
        "        stale=True,\n"
        "        # Cost was mirrored into the snapshot by broadcast_context_usage,\n"
        "        # so Spent survives a restart/expiry like the bar does.\n"
        "        cost=snapshot.get(\"cost\"),\n"
        "    )\n",
    ),
]

failures = 0
for path, old, new in EDITS:
    text = path.read_text()
    if text.count(old) != 1:
        print(f"FAIL {path.name}: expected exactly 1 match, found {text.count(old)}")
        failures += 1
        continue
    if not path.exists():
        pass
    backup = path.with_suffix(path.suffix + ".seedcostbak")
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new))
    print(f"OK   {path.name}")

sys.exit(1 if failures else 0)
