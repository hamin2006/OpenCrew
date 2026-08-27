#!/usr/bin/env python3
"""Treat opencode's native /compact as a successful compaction.

opencode compacts INLINE: its /compact prompt completes the turn only after
session.summarize ran (verified empirically: the following usage_update
reports the compacted context, e.g. 61,327 -> 12,336 tokens), but it never
emits _kiro.dev/compaction/status. Kiro therefore waited out the full
COMPACT_WAIT_TIMEOUT, reported "timed out", counted a failure (cooldown +
circuit breaker) and eventually RECYCLED the session (kill + drop sid) even
though the compact succeeded.

The ses_* sid prefix is opencode's id shape (kiro-cli/KAS use UUIDs), so a
prompt-turn completion with no status event on such a session IS the success
signal.
"""
import pathlib
import sys

WHEEL = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew"
)
HANDLE = WHEEL / "acp/session_handle.py"
PROVIDER = WHEEL / "providers/acp.py"

HANDLE_OLD = (
    "        self._compact_result = None\n"
    "        async for event in self.prompt(cmd):\n"
    "            if event.kind == EVENT_COMPACTION_STATUS and event.text in (\n"
    "                \"completed\",\n"
    "                \"failed\",\n"
    "            ):\n"
    "                self._compact_result = {\n"
    "                    \"type\": event.text,\n"
    "                    \"summary\": event.title or \"\",\n"
    "                }\n"
)
HANDLE_NEW = HANDLE_OLD + (
    "        if self._compact_result is None and self._session_id.startswith(\"ses_\"):\n"
    "            # opencode compacts natively and emits no\n"
    "            # _kiro.dev/compaction/status: the /compact turn completes\n"
    "            # only after session.summarize ran (the following\n"
    "            # usage_update reports the compacted context). Marking the\n"
    "            # prompt completion as success stops the caller from timing\n"
    "            # out and counting a successful compact as a failure\n"
    "            # (cooldown -> circuit breaker -> session recycle).\n"
    "            self._compact_result = {\"type\": \"completed\", \"summary\": \"\"}\n"
)

PROVIDER_OLD = (
    "        self._compact_result = None\n"
    "        async for event in self._client.stream_events(message):\n"
    "            if event.kind == EVENT_COMPACTION_STATUS and event.text in (\n"
    "                \"completed\",\n"
    "                \"failed\",\n"
    "            ):\n"
    "                self._compact_result = {\n"
    "                    \"type\": event.text,\n"
    "                    \"summary\": event.title or \"\",\n"
    "                }\n"
)
PROVIDER_NEW = PROVIDER_OLD + (
    "        if self._compact_result is None:\n"
    "            _sid = getattr(self._client, \"session_id\", None) or \"\"\n"
    "            if _sid.startswith(\"ses_\"):\n"
    "                # opencode compacts natively and emits no\n"
    "                # _kiro.dev/compaction/status: the /compact turn completes\n"
    "                # only after session.summarize ran (the following\n"
    "                # usage_update reports the compacted context). Marking the\n"
    "                # prompt completion as success stops the caller from\n"
    "                # timing out and counting a successful compact as a\n"
    "                # failure (cooldown -> circuit breaker -> recycle).\n"
    "                self._compact_result = {\"type\": \"completed\", \"summary\": \"\"}\n"
)

EDITS = [(HANDLE, HANDLE_OLD, HANDLE_NEW), (PROVIDER, PROVIDER_OLD, PROVIDER_NEW)]

failures = 0
for path, old, new in EDITS:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL {path.name}: expected exactly 1 match, found {count}")
        failures += 1
        continue
    backup = path.with_suffix(path.suffix + ".compactbak")
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new))
    print(f"OK   {path.name}")

sys.exit(1 if failures else 0)
