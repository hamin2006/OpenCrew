#!/usr/bin/env python3
"""Unify the skill surface: kiro's dir becomes canonical, opencode's dir
becomes a symlink to it. Agent-added skills (written to ~/.kiro/crew/skills)
then appear in opencode automatically, and opencode's original skills show in
the kiro dashboard picker.
"""
import pathlib
import shutil

KIRO = pathlib.Path.home() / ".kiro/crew/skills"
OPENCODE = pathlib.Path.home() / ".config/opencode/skills"

ORIGINALS = [
    "copywriting", "docx", "frontend-design", "humanizer", "kimi-webbridge",
    "mcp-builder", "pc-dev", "pdf", "pptx", "research", "skill-creator",
    "webapp-testing", "xlsx",
]

# 1. Copy opencode's original skills into the canonical kiro dir.
for name in ORIGINALS:
    src = OPENCODE / name
    if not src.is_dir():
        print(f"skip  {name} (missing)")
        continue
    dst = KIRO / name
    if dst.exists():
        print(f"exist {name}")
        continue
    shutil.copytree(src, dst)
    print(f"move  {name}")

# 2. Replace opencode's skills dir with a symlink to the canonical dir.
if OPENCODE.is_symlink():
    print("opencode skills dir is already a symlink")
else:
    backup = OPENCODE.with_name("skills.premerge")
    if not backup.exists():
        OPENCODE.rename(backup)
        print(f"backed up old skills dir -> {backup.name}")
    OPENCODE.symlink_to(KIRO, target_is_directory=True)
    print("symlinked ~/.config/opencode/skills -> ~/.kiro/crew/skills")

print("canonical dir entries:", len(list(KIRO.iterdir())))
print("via symlink:", len(list(OPENCODE.iterdir())))
