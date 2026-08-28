#!/usr/bin/env python3
"""Gate mid-turn steer for opencode sessions.

opencode implements no _session/steer — the fire-and-forget send was silently
dropped (a Telegram mid-turn redirect vanished: not injected, not queued).
Returning False from steer()/supports_steer routes the message through the
caller's graceful fallback (re-run/queued after the turn).
"""
import pathlib
import sys

HANDLE = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/acp/session_handle.py"
)

EDITS = [
    (
        "    @property\n"
        "    def supports_steer(self) -> bool:\n"
        '        """True — AcpRuntime is kiro-cli only, which supports _session/steer."""\n'
        "        return True\n",
        "    @property\n"
        "    def supports_steer(self) -> bool:\n"
        '        """True for kiro-cli, which supports ``_session/steer``.\n'
        "\n"
        "        opencode has no steer extension — a fire-and-forget send would\n"
        "        be silently dropped (the redirect text would vanish, not even\n"
        "        queue for the next turn). Gating it off routes steers through\n"
        "        the caller's graceful fallback (re-run/queued after the turn).\n"
        '        """\n'
        '        return not self._session_id.startswith("ses_")\n',
    ),
    (
        "        text = (message or \"\").strip()\n"
        "        if not text or not self._session_id:\n"
        "            return False\n"
        "        wrapped = f\"<user_message>\\n{text}\\n</user_message>\"\n",
        "        text = (message or \"\").strip()\n"
        "        if not text or not self._session_id:\n"
        "            return False\n"
        '        if self._session_id.startswith("ses_"):\n'
        "            # opencode implements no _session/steer — a fire-and-forget\n"
        "            # send would be silently dropped. False routes the message\n"
        "            # through the caller's queue/re-run fallback instead.\n"
        "            return False\n"
        "        wrapped = f\"<user_message>\\n{text}\\n</user_message>\"\n",
    ),
]

failures = 0
for old, new in EDITS:
    text = HANDLE.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL: expected exactly 1 match, found {count} for: {old[:60]!r}")
        failures += 1
        continue
    backup = HANDLE.with_suffix(HANDLE.suffix + ".steerbak")
    if not backup.exists():
        backup.write_text(text)
    HANDLE.write_text(text.replace(old, new))
    print("OK   session_handle.py")

sys.exit(1 if failures else 0)
