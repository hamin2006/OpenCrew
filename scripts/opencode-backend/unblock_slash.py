#!/usr/bin/env python3
"""Unblock /tools, /mcp, /logdump, /hooks — now implemented gateway-local."""
import pathlib

PATH = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_utils.py"
)

OLD = '    {"/quit", "/exit", "/q", "/chat", "/paste", "/reply", "/editor", "/tangent", "/issue", "/experiment", "/code", "/side", "/tools", "/mcp", "/logdump", "/hooks"}\n'
NEW = '    {"/quit", "/exit", "/q", "/chat", "/paste", "/reply", "/editor", "/tangent", "/issue", "/experiment", "/code", "/side"}\n'

text = PATH.read_text(encoding="utf-8")
count = text.count(OLD)
assert count == 1, f"expected 1 match, found {count}"
backup = PATH.with_suffix(PATH.suffix + ".unblkbak")
if not backup.exists():
    backup.write_text(text, encoding="utf-8")
PATH.write_text(text.replace(OLD, NEW), encoding="utf-8")
print("OK   unblocked 4 commands in chat_utils.py")
