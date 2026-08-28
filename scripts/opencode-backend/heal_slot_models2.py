#!/usr/bin/env python3
"""Wire _normalize_slot_models into both async restores (anchor fix)."""
import pathlib

PATH = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_persistence.py"
)


def patch(old: str, new: str, label: str) -> None:
    t = PATH.read_text(encoding="utf-8")
    n = t.count(old)
    if n != 1:
        raise SystemExit(f"FAIL {label}: expected 1 match, found {n}")
    b = PATH.with_suffix(PATH.suffix + ".healbak2")
    if not b.exists():
        b.write_text(t, encoding="utf-8")
    PATH.write_text(t.replace(old, new), encoding="utf-8")
    print(f"OK   {label}")


patch(
    """    finally:
        # Always clear, even if a rehydrate raises \u2014 a stuck flag would silently
        # disable open-tab persistence for the rest of the process's life.
        state.restoring_open_slots = False
    return restored
""",
    """    finally:
        # Always clear, even if a rehydrate raises \u2014 a stuck flag would silently
        # disable open-tab persistence for the rest of the process's life.
        state.restoring_open_slots = False
    await _normalize_slot_models(state)
    return restored
""",
    "open_slots restore hook",
)

patch(
    """    finally:
        state.restoring_open_slots = False
    return restored
""",
    """    finally:
        state.restoring_open_slots = False
    await _normalize_slot_models(state)
    return restored
""",
    "recent_sessions restore hook",
)

print("ALL DONE")
