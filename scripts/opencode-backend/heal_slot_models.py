#!/usr/bin/env python3
"""One-time heal: normalize persisted wire-id slot.model pins to display labels.

Runs after both async slot restores so slots pinned before the label-first
pick change stop rendering "isn't offered right now" without a re-pick.
"""
import pathlib

PATH = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_persistence.py"
)

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


def patch(old: str, new: str, label: str) -> None:
    t = PATH.read_text(encoding="utf-8")
    n = t.count(old)
    if n != 1:
        raise SystemExit(f"FAIL {label}: expected 1 match, found {n}")
    b = PATH.with_suffix(PATH.suffix + ".healbak")
    if not b.exists():
        b.write_text(t, encoding="utf-8")
    PATH.write_text(t.replace(old, new), encoding="utf-8")
    print(f"OK   {label}")


if "def _normalize_slot_models" not in PATH.read_text(encoding="utf-8"):
    t = PATH.read_text(encoding="utf-8")
    b = PATH.with_suffix(PATH.suffix + ".healbak")
    if not b.exists():
        b.write_text(t, encoding="utf-8")
    PATH.write_text(HELPER + t, encoding="utf-8")
    print("OK   helper added")
else:
    print("SKIP helper (present)")

patch(
    """    finally:
        state.restoring_open_slots = False
    return restored


def _attach_variants""",
    """    finally:
        state.restoring_open_slots = False
    await _normalize_slot_models(state)
    return restored


def _attach_variants""",
    "open_slots restore hook",
)

patch(
    """    finally:
        state.restoring_open_slots = False
    return restored


def _diff_dropped_message_lines""",
    """    finally:
        state.restoring_open_slots = False
    await _normalize_slot_models(state)
    return restored


def _diff_dropped_message_lines""",
    "recent_sessions restore hook",
)

print("ALL DONE")
