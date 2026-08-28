#!/usr/bin/env python3
"""Temporary debug: log the /model configOptions read."""
import pathlib

p = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_runner.py"
)
t = p.read_text()
old = (
    '            for _opt in _opts or []:\n'
    '                if isinstance(_opt, dict) and _opt.get("id") == "model":'
)
new = (
    '            logger.warning(\n'
    '                "SLASHDBG client=%r opts=%r",\n'
    "                type(_client).__name__,\n"
    '                [o.get("id") if isinstance(o, dict) else None for o in (_opts or [])][:10],\n'
    "            )\n"
    '            for _opt in _opts or []:\n'
    '                if isinstance(_opt, dict) and _opt.get("id") == "model":'
)
assert t.count(old) == 1, t.count(old)
p.write_text(t.replace(old, new))
print("debug added")
