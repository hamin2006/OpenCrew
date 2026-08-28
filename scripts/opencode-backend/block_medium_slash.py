#!/usr/bin/env python3
"""Block the un-implemented medium-effort slash commands (/tools, /mcp,
/logdump, /hooks) — silent no-ops with opencode. /prompts has a local handler
and stays."""
import pathlib
import sys

UTILS = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_utils.py"
)

EDITS = [
    (UTILS, '        "/hooks",\n', ""),
    (UTILS, '        "/logdump",\n', ""),
    (UTILS, '        "/mcp",\n', ""),
    (UTILS, '        "/tools",\n', ""),
    (
        UTILS,
        '    {"/quit", "/exit", "/q", "/chat", "/paste", "/reply", "/editor", "/tangent",'
        ' "/issue", "/experiment", "/code", "/side"}\n',
        '    {"/quit", "/exit", "/q", "/chat", "/paste", "/reply", "/editor", "/tangent",'
        ' "/issue", "/experiment", "/code", "/side", "/tools", "/mcp", "/logdump", "/hooks"}\n',
    ),
]

failures = 0
for path, old, new in EDITS:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL: expected exactly 1 match, found {count} for: {old[:50]!r}")
        failures += 1
        continue
    backup = path.with_suffix(path.suffix + ".blkbak")
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new))
    print("OK   chat_utils.py")

sys.exit(1 if failures else 0)
