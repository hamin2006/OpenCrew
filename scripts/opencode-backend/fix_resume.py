#!/usr/bin/env python3
"""Accept opencode-style session/load responses (configOptions, no modes).

kiro-cli/KAS echo ``modes`` on a genuine resume; opencode's successful
``session/load`` returns ``{configOptions: [...]}`` only, which the gateway
misread as a failed resume (runtime) or silently fell back to a fresh session
(client). Additionally the client's transcript gate (kiro-cli storage layout)
never finds an opencode transcript, so opencode resumes were skipped entirely.

Patch 1 (client.py):        ses_* sids skip the transcript gate + get no
                            _meta._kiro.dev/session_file; load success accepts
                            configOptions as well as modes.
Patch 2 (runtime.py):       load_session success accepts configOptions too.
"""
import pathlib
import sys

WHEEL = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew"
)
CLIENT = WHEEL / "acp/client.py"
RUNTIME = WHEEL / "acp/runtime.py"

EDITS = [
    (
        CLIENT,
        "            else:\n"
        "                session_file = str(\n"
        "                    kiro_sessions_dir() / f\"{resume_sid}.json\"\n"
        "                )\n"
        "                file_ok = Path(session_file).exists()\n",
        "            else:\n"
        "                session_file = str(\n"
        "                    kiro_sessions_dir() / f\"{resume_sid}.json\"\n"
        "                )\n"
        "                # kiro-cli stores its transcripts at that path; an\n"
        "                # opencode sid (ses_*) never does. opencode resolves\n"
        "                # the sid itself and errors on unknown ids, so a ses_\n"
        "                # sid skips the transcript gate and is loaded with no\n"
        "                # file path advertised.\n"
        "                _opencode_sid = resume_sid.startswith(\"ses_\")\n"
        "                file_ok = Path(session_file).exists() or _opencode_sid\n"
        "                if _opencode_sid:\n"
        "                    session_file = \"\"\n",
    ),
    (
        CLIENT,
        "                    if self._is_claude:\n"
        "                        load_params[\"_meta\"] = {\"claudeCode\": {\"options\": {}}}\n"
        "                    else:\n"
        "                        load_params[\"_meta\"] = {\"_kiro.dev/session_file\": session_file}\n",
        "                    if self._is_claude:\n"
        "                        load_params[\"_meta\"] = {\"claudeCode\": {\"options\": {}}}\n"
        "                    elif session_file:\n"
        "                        load_params[\"_meta\"] = {\"_kiro.dev/session_file\": session_file}\n",
    ),
    (
        CLIENT,
        "                    load_id = await self._send_request(METHOD_SESSION_LOAD, load_params)\n"
        "                    load_resp = await self._wait_for_response(load_id, timeout=_INIT_TIMEOUT)\n"
        "                    if \"modes\" in load_resp:\n",
        "                    load_id = await self._send_request(METHOD_SESSION_LOAD, load_params)\n"
        "                    load_resp = await self._wait_for_response(load_id, timeout=_INIT_TIMEOUT)\n"
        "                    # A genuine kiro-cli/KAS resume echoes \"modes\";\n"
        "                    # opencode's successful load returns a\n"
        "                    # configOptions-only payload. Accept either.\n"
        "                    if \"modes\" in load_resp or \"configOptions\" in load_resp:\n",
    ),
    (
        RUNTIME,
        "            # A genuine resume echoes \"modes\" in the response (same signal AcpClient\n"
        "            # keys on). Anything else means load did not actually restore state.\n"
        "            if \"modes\" not in resp:\n"
        "                raise AcpRuntimeError(\n"
        "                    f\"session/load did not resume session {resume_sid}: {resp}\"\n"
        "                )\n",
        "            # A genuine resume echoes \"modes\" in the response (same\n"
        "            # signal AcpClient keys on); opencode-style backends instead\n"
        "            # return a configOptions-only payload on a successful load.\n"
        "            # Anything else means load did not actually restore state.\n"
        "            if \"modes\" not in resp and \"configOptions\" not in resp:\n"
        "                raise AcpRuntimeError(\n"
        "                    f\"session/load did not resume session {resume_sid}: {resp}\"\n"
        "                )\n",
    ),
]

failures = 0
for path, old, new in EDITS:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL {path.name}: expected exactly 1 match, found {count}")
        failures += 1
        continue
    backup = path.with_suffix(path.suffix + ".resumebak")
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new))
    print(f"OK   {path.name}")

sys.exit(1 if failures else 0)
