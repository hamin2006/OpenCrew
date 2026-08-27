#!/usr/bin/env python3
"""Re-apply the heal cleanly: helper inserted AFTER `from __future__` line."""
import pathlib

PATH = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_persistence.py"
)
BACKUP = PATH.with_suffix(PATH.suffix + ".healbak")

HELPER = '''


async def _normalize_slot_models(state: "DashboardState") -> None:
    """Rewrite wire-id ``slot.model`` pins to display labels (one-time heal).

    Before the label-first pick change, the pick API stored opencode
    provider/model wire ids in ``slot.model``; the frontend's "offered" list
    is label-keyed (``model_name``), so a wire pin rendered as "not offered".
    Migrate persisted pins so the fix applies to already-pinned slots without
    a re-pick. Labels pass through; unknown wire ids are left untouched.
    """
    try:
        from kiro_crew.dashboard.chat_handlers import _opencode_model_catalog
    except Exception:
        return
    try:
        catalog = await _opencode_model_catalog()
    except Exception:
        return
    if not catalog:
        return
    for slot in state._slots.values():
        cur = slot.model
        if not cur or cur == "auto" or "/" not in cur:
            continue
        label = next(
            (
                k
                for k, v in catalog.items()
                if v == cur and k != cur and " (" in k
            ),
            None,
        )
        if label and label != cur:
            slot.model = label


'''

# 1. Restore the pristine file.
if BACKUP.exists():
    PATH.write_text(BACKUP.read_text(encoding="utf-8"), encoding="utf-8")
    print("OK   restored from .healbak")
else:
    raise SystemExit("no .healbak backup found")

# 2. Insert the helper after the `from __future__ import annotations` line.
t = PATH.read_text(encoding="utf-8")
anchor = "from __future__ import annotations\n"
assert t.count(anchor) == 1, "future import not found"
b = PATH.with_suffix(PATH.suffix + ".healbak")
b.write_text(t, encoding="utf-8")
PATH.write_text(t.replace(anchor, anchor + HELPER), encoding="utf-8")
print("OK   helper inserted after future import")
