#!/usr/bin/env python3
"""Fix the telegram /model parser: opencode models --verbose emits PRETTY-PRINTED
(multi-line) JSON objects after a non-JSON header line, so the single-line
parser found nothing. Mirror agents.py's buffered accumulation."""
import pathlib
import sys

DISPATCH = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/telegram/transport_dispatch.py"
)

OLD = (
    "            rows: list[tuple[str, str]] = []\n"
    "            for line in stdout.decode(errors=\"replace\").splitlines():\n"
    "                line = line.strip()\n"
    "                if not line.startswith(\"{\"):\n"
    "                    continue\n"
    "                try:\n"
    "                    m = json.loads(line)\n"
    "                except json.JSONDecodeError:\n"
    "                    continue\n"
    "                if not isinstance(m, dict):\n"
    "                    continue\n"
    "                mid = m.get(\"id\")\n"
    "                pid = m.get(\"providerID\")\n"
    "                if not isinstance(mid, str) or not isinstance(pid, str):\n"
    "                    continue\n"
    "                rows.append(\n"
    "                    (\n"
    "                        f\"{pid}/{mid}\",\n"
    "                        f\"{m.get('name') or mid} ({_PROVIDER_DISPLAY.get(pid, pid)})\",\n"
    "                    )\n"
    "                )\n"
    "            return rows\n"
)

NEW = (
    "            # Output is one PRETTY-PRINTED (multi-line) JSON object per\n"
    "            # model after a non-JSON header line — accumulate lines into\n"
    "            # a buffer until one parses, mirroring agents.api_models.\n"
    "            rows: list[tuple[str, str]] = []\n"
    "            buf = \"\"\n"
    "            for line in stdout.decode(errors=\"replace\").splitlines():\n"
    "                if line.lstrip().startswith(\"{\"):\n"
    "                    buf = line\n"
    "                    continue\n"
    "                if buf:\n"
    "                    buf += \"\\n\" + line\n"
    "                    try:\n"
    "                        m = json.loads(buf)\n"
    "                    except json.JSONDecodeError:\n"
    "                        continue\n"
    "                    buf = \"\"\n"
    "                    if not isinstance(m, dict):\n"
    "                        continue\n"
    "                    mid = m.get(\"id\")\n"
    "                    pid = m.get(\"providerID\")\n"
    "                    if not isinstance(mid, str) or not isinstance(pid, str):\n"
    "                        continue\n"
    "                    rows.append(\n"
    "                        (\n"
    "                            f\"{pid}/{mid}\",\n"
    "                            f\"{m.get('name') or mid} ({_PROVIDER_DISPLAY.get(pid, pid)})\",\n"
    "                        )\n"
    "                    )\n"
    "            return rows\n"
)

text = DISPATCH.read_text()
count = text.count(OLD)
if count != 1:
    print(f"FAIL: expected exactly 1 match, found {count}")
    sys.exit(1)
DISPATCH.write_text(text.replace(OLD, NEW))
print("OK parser fixed")
