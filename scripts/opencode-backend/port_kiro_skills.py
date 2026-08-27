#!/usr/bin/env python3
"""Port the kiro skills to opencode's skills dir.

Straight copy (frontmatter is compatible; opencode ignores the extra
`triggers` key). Skipped: computer-use + ios-simulator-preview (macOS-only,
this host is headless Linux) and kirocrew-dev (kiro-internal, no description).
"""
import pathlib
import shutil

SRC = pathlib.Path.home() / ".kiro/crew/skills"
DST = pathlib.Path.home() / ".config/opencode/skills"

SKIP = {"computer-use", "ios-simulator-preview", "kirocrew-dev"}

DST.mkdir(parents=True, exist_ok=True)
for skill_dir in sorted(SRC.iterdir()):
    if not skill_dir.is_dir():
        continue
    name = skill_dir.name
    if name in SKIP:
        print(f"skip  {name}")
        continue
    if (DST / name).exists():
        print(f"exist {name} (already ported)")
        continue
    shutil.copytree(skill_dir, DST / name)
    print(f"port  {name}")

print("\nopencode skills now:", len(list(DST.iterdir())))
