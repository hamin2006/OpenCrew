#!/usr/bin/env python3
"""Use the session provider's acp_config_options() accessor for configOptions.

AcpProvider._client is the AcpSessionProvider (not the raw handle), so
`_config_options` is absent there — the model/mode resolution silently read
None. The session provider exposes acp_config_options() (handle.config_options).
"""
import pathlib
import sys

RUNNER = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_runner.py"
)
HANDLERS = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_handlers.py"
)

RUNNER_OLD = '            for _opt in getattr(_client, "_config_options", None) or []:\n'
RUNNER_NEW = (
    "            _opts = (\n"
    '                _client.acp_config_options()\n'
    '                if callable(getattr(_client, "acp_config_options", None))\n'
    '                else getattr(_client, "_config_options", None)\n'
    "            )\n"
    "            for _opt in _opts or []:\n"
)

HANDLERS_OLD = '        for _opt in getattr(_client, "_config_options", None) or []:\n'
HANDLERS_NEW = (
    "        _opts = (\n"
    '            _client.acp_config_options()\n'
    '            if callable(getattr(_client, "acp_config_options", None))\n'
    '            else getattr(_client, "_config_options", None)\n'
    "        )\n"
    "        for _opt in _opts or []:\n"
)

failures = 0

text = RUNNER.read_text()
count = text.count(RUNNER_OLD)
if count != 2:
    print(f"FAIL runner: expected 2 matches, found {count}")
    failures += 1
else:
    RUNNER.write_text(text.replace(RUNNER_OLD, RUNNER_NEW))
    print("OK   chat_runner.py (2 spots)")

text = HANDLERS.read_text()
count = text.count(HANDLERS_OLD)
if count != 1:
    print(f"FAIL handlers: expected 1 match, found {count}")
    failures += 1
else:
    HANDLERS.write_text(text.replace(HANDLERS_OLD, HANDLERS_NEW))
    print("OK   chat_handlers.py")

sys.exit(1 if failures else 0)
