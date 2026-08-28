#!/usr/bin/env python3
"""1. Drop high-effort slash commands (keep /goal); 2. install the goal skill;
3. wire /goal (and plan goals) to reference the skill."""
import pathlib
import sys

WHEEL = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew"
)
UTILS = WHEEL / "dashboard/chat_utils.py"
RUNNER = WHEEL / "dashboard/chat_runner.py"
ORCH = WHEEL / "dashboard/chat_orchestrator.py"

EDITS = [
    # ── A1: remove /issue from _SLASH_COMMANDS ──
    (UTILS, '        "/issue",\n', ""),
    # ── A2: remove /experiment ──
    (UTILS, '        "/experiment",\n', ""),
    # ── A3: remove /code ──
    (UTILS, '        "/code",\n', ""),
    # ── A4: remove /side ──
    (UTILS, '        "/side",\n', ""),
    # ── A5: block them (hidden from suggestions, ⚠️ on use) ──
    (
        UTILS,
        '    {"/quit", "/exit", "/q", "/chat", "/paste", "/reply", "/editor", "/tangent"}\n',
        '    {"/quit", "/exit", "/q", "/chat", "/paste", "/reply", "/editor", "/tangent",'
        ' "/issue", "/experiment", "/code", "/side"}\n',
    ),
    # ── B: nudge references the goal skill ──
    (
        RUNNER,
        "            _nudge = (\n"
        '                f"Goal: {_objective}\\n"\n'
        '                "Each idle cycle, in order: "\n',
        "            _nudge = (\n"
        '                f"Goal: {_objective}\\n"\n'
        '                "Follow the `goal` skill (load it with the skill tool) for the goal "\n'
        '                "structure: measurable Definition of Done, todos tracking, one atomic "\n'
        '                "step per cycle, evidence-based completion.\\n"\n'
        '                "Each idle cycle, in order: "\n',
    ),
    # ── C: plan-stage goal injection references the skill ──
    (
        ORCH,
        '    if goal:\n        parts.append(f"🎯 Goal: {goal}")\n',
        '    if goal:\n'
        '        parts.append(\n'
        '            f"🎯 Goal: {goal} — follow the `goal` skill (Definition of Done, todos, "\n'
        '            "one step per cycle, evidence-based completion)."\n'
        "        )\n",
    ),
]

failures = 0
for path, old, new in EDITS:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL {path.name}: expected exactly 1 match, found {count} for: {old[:50]!r}")
        failures += 1
        continue
    backup = path.with_suffix(path.suffix + ".goalbak")
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new))
    print(f"OK   {path.name}")

# ── goal skill into the shared skills dir ──
SKILL = pathlib.Path.home() / ".kiro/crew/skills/goal/SKILL.md"
SKILL.parent.mkdir(parents=True, exist_ok=True)
SKILL.write_text(
    "---\n"
    "name: goal\n"
    "description: Manage a goal through to completion — define a measurable Definition of Done, "
    "track progress in todos, advance one concrete step per cycle, and verify with evidence before "
    "claiming done. Use when the user sets a goal (chat /goal or the Set a goal button), asks you "
    "to work toward an objective, or a goal loop is active.\n"
    "---\n"
    "\n"
    "# Goal Management\n"
    "\n"
    "## When a goal is active\n"
    "You are working toward a user-set goal, typically one step per cycle in an\n"
    "unattended loop. Follow this structure every cycle.\n"
    "\n"
    "## 1. Define the goal (first cycle)\n"
    "- Restate the goal as a measurable outcome with a Definition of Done (DoD):\n"
    "  what evidence proves completion (a passing test, a built artifact, specific\n"
    "  output)?\n"
    "- Record the DoD in your todos so every cycle can check against it.\n"
    "\n"
    "## 2. Track progress in todos\n"
    "- Keep an up-to-date todos list: the goal, its DoD, the current step, and\n"
    "  what is left.\n"
    "- Update it at the end of every cycle.\n"
    "\n"
    "## 3. One atomic step per cycle\n"
    "- Do exactly ONE concrete step (<=5 tool calls): investigate, build, or fix.\n"
    "- Make the deliverable durable before claiming progress — write the file, run\n"
    "  the check, capture the output.\n"
    "- Report one short progress line.\n"
    "\n"
    "## 4. Completion check (every cycle)\n"
    "- Verify against the DoD with concrete evidence (a passing test, a built file,\n"
    "  command output) — not a guess.\n"
    "- If met: stop, post a one-line summary citing the evidence.\n"
    "- If blocked: state the blocker once, then stop rather than repeating.\n"
    "\n"
    "## Guardrails\n"
    "- Never git push without explicit permission.\n"
    "- Never read credential files.\n"
    "- Stay within the cycle budget; the loop stops at the cap.\n"
)
print("OK   goal skill written")

sys.exit(1 if failures else 0)
