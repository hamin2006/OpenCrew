#!/usr/bin/env python3
"""Make wait_for_compaction treat opencode turn completion as success.

The dashboard /compact path never calls compact() — the message is streamed
as a normal turn, then wait_for_compaction() is called directly. opencode
emits no _kiro.dev/compaction/status, so the queue drain consumed the full
COMPACT_WAIT_TIMEOUT and callers counted a successful compact as a timeout
(cooldown -> circuit breaker -> session recycle).

For ses_* (opencode) sessions the /compact turn completing IS the completion
signal: opencode runs session.summarize before ending the turn, and the
usage_update reporting the compacted context has already been processed.
"""
import pathlib
import sys

WHEEL = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew"
)
HANDLE = WHEEL / "acp/session_handle.py"
PROVIDER = WHEEL / "providers/acp.py"

HANDLE_OLD = (
    "            return cached\n"
    "        deadline = time.monotonic() + timeout\n"
)
HANDLE_NEW = (
    "            return cached\n"
    "        if self._session_id.startswith(\"ses_\"):\n"
    "            # opencode compacts inline: the /compact turn completing IS\n"
    "            # the completion signal — it emits no\n"
    "            # _kiro.dev/compaction/status, so the queue drain below\n"
    "            # would wait out the full timeout and the caller would count\n"
    "            # a successful compact as a failure (cooldown -> circuit\n"
    "            # breaker -> session recycle). The usage_update reporting\n"
    "            # the compacted context was already processed by the\n"
    "            # dispatch loop; a brief drain lets any trailing frame land\n"
    "            # before callers broadcast.\n"
    "            await self._drain_post_compaction_metadata()\n"
    "            return {\"type\": \"completed\", \"summary\": \"\"}\n"
    "        deadline = time.monotonic() + timeout\n"
)

PROVIDER_OLD = (
    "            return cached\n"
    "        return await self._client.wait_for_compaction(timeout)\n"
)
PROVIDER_NEW = (
    "            return cached\n"
    "        _sid = getattr(self._client, \"session_id\", None) or \"\"\n"
    "        if _sid.startswith(\"ses_\"):\n"
    "            # opencode compacts inline: the /compact turn completing IS\n"
    "            # the completion signal (no _kiro.dev/compaction/status\n"
    "            # exists), so the delegated queue wait would time out and\n"
    "            # the caller would count a successful compact as a failure\n"
    "            # (cooldown -> circuit breaker -> session recycle).\n"
    "            drain = getattr(self._client, \"_drain_post_compaction_metadata\", None)\n"
    "            if drain is not None:\n"
    "                await drain()\n"
    "            return {\"type\": \"completed\", \"summary\": \"\"}\n"
    "        return await self._client.wait_for_compaction(timeout)\n"
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
    backup = path.with_suffix(path.suffix + ".waitbak")
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new))
    print(f"OK   {path.name}")

sys.exit(1 if failures else 0)
