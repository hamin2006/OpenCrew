#!/usr/bin/env python3
"""Item 1 + 3: effort routing via set_config_option for opencode; kas session sharing.

Effort: change_effort/clear_effort sent /effort via _kiro.dev/commands/execute
for non-claude backends — a method opencode does not implement (hard error,
rollback). opencode's session/set_config_option accepts the effort config
option (its configOptions advertise low/high/max), so opencode-style sessions
(ses_* sids) route there instead.

Sharing: KAS was excluded from ACP_BACKENDS_SESSION_SHARING because the KAS
teardown verb deletes the session record, stranding spawn_continue. That does
not apply to an opencode-backed KAS: the delete verb is a best-effort no-op
opencode (it keeps its own storage), SessionMap skips file checks for non-kiro
providers, sid validity is decided by session/load (already fixed), and shared-
arm teardown is retain-by-default. So the blocker is resolved for this harness.
"""
import pathlib
import sys

WHEEL = pathlib.Path(
    "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew"
)
ACP = WHEEL / "providers/acp.py"
TYPES = WHEEL / "acp/types.py"

EDITS = [
    # ── Edit 1: _is_opencode_style property ──
    (
        ACP,
        "    @property\n"
        "    def is_kas_backend(self) -> bool:\n"
        "        \"\"\"True when this ACP provider talks to KAS (kiro-agent).\"\"\"\n"
        "        return self._client.backend == ACP_BACKEND_KAS\n"
        "\n"
        "    @property\n"
        "    def is_kiro_backend(self) -> bool:\n",
        "    @property\n"
        "    def is_kas_backend(self) -> bool:\n"
        "        \"\"\"True when this ACP provider talks to KAS (kiro-agent).\"\"\"\n"
        "        return self._client.backend == ACP_BACKEND_KAS\n"
        "\n"
        "    @property\n"
        "    def _is_opencode_style(self) -> bool:\n"
        "        \"\"\"True when the backing session is opencode-shaped (``ses_*`` sid).\n"
        "\n"
        "        opencode resolves session ids in its own storage, so resume and\n"
        "        config-option pushes use ACP verbs (session/load,\n"
        "        session/set_config_option) rather than kiro-cli's commands/execute\n"
        "        overlay machinery.\n"
        "        \"\"\"\n"
        "        sid = getattr(self._client, \"session_id\", None) or \"\"\n"
        "        return str(sid).startswith(\"ses_\")\n"
        "\n"
        "    @property\n"
        "    def is_kiro_backend(self) -> bool:\n",
    ),
    # ── Edit 2: change_effort routing ──
    (
        ACP,
        "        try:\n"
        "            if self.is_claude_backend:\n"
        "                await self._set_claude_effort(level)\n"
        "            else:\n"
        "                await self._client.send_command(\"/effort\", args={\"level\": level})\n"
        "        except Exception:\n",
        "        try:\n"
        "            if self.is_claude_backend:\n"
        "                await self._set_claude_effort(level)\n"
        "            elif self._is_opencode_style:\n"
        "                # opencode has no commands/execute: set the effort\n"
        "                # config option directly (session/set_config_option\n"
        "                # validates against the advertised effort levels).\n"
        "                await self._client.set_config_option(\"effort\", level)\n"
        "            else:\n"
        "                await self._client.send_command(\"/effort\", args={\"level\": level})\n"
        "        except Exception:\n",
    ),
    # ── Edit 3: clear_effort routing ──
    (
        ACP,
        "        # kiro: clear/rewrite the overlay so a respawn doesn't re-apply it.\n"
        "        level = self._resolve_effort()  # workspace default, or None\n"
        "        if level:\n"
        "            self._apply_effort_overlay()\n"
        "            await self._client.send_command(\"/effort\", args={\"level\": level})\n"
        "            logger.info(\"ACP effort cleared to workspace default %s (kiro)\", level)\n"
        "            return True\n",
        "        # kiro/opencode: clear/rewrite the overlay so a respawn doesn't\n"
        "        # re-apply it; a resolvable workspace default is pushed live.\n"
        "        level = self._resolve_effort()  # workspace default, or None\n"
        "        if level:\n"
        "            self._apply_effort_overlay()\n"
        "            if self._is_opencode_style:\n"
        "                await self._client.set_config_option(\"effort\", level)\n"
        "                logger.info(\n"
        "                    \"ACP effort cleared to workspace default %s (opencode)\", level\n"
        "                )\n"
        "            else:\n"
        "                await self._client.send_command(\"/effort\", args={\"level\": level})\n"
        "                logger.info(\n"
        "                    \"ACP effort cleared to workspace default %s (kiro)\", level\n"
        "                )\n"
        "            return True\n",
    ),
    # ── Edit 4: sharing membership + comment ──
    (
        TYPES,
        "# which removes the persisted session — so a shared subagent would strand\n"
        "# spawn_continue (conversation_gone). KAS therefore opts in only once a\n"
        "# keep-aware teardown lands (native subagent work); until then its subagents get\n"
        "# dedicated sessions. claude-agent-acp runs through AcpClient (one process per\n"
        "# session) and is not a member.\n"
        "ACP_BACKENDS_SESSION_SHARING = frozenset({ACP_BACKEND_KIRO})\n",
        "# which removes the persisted session — so a shared subagent would strand\n"
        "# spawn_continue (conversation_gone). KAS is admitted because the teardown\n"
        "# concern does not apply to an opencode-backed KAS: the delete verb is a\n"
        "# best-effort no-op there (opencode keeps its own storage), SessionMap skips\n"
        "# file checks for non-kiro providers, and sid validity is decided by\n"
        "# session/load — so shared-arm sessions stay resumable. claude-agent-acp runs\n"
        "# through AcpClient (one process per session) and is not a member.\n"
        "ACP_BACKENDS_SESSION_SHARING = frozenset({ACP_BACKEND_KIRO, ACP_BACKEND_KAS})\n",
    ),
    # ── Edit 5: stale clause in the ACP_RUNTIME comment ──
    (
        TYPES,
        "# AcpRuntime is necessary for session sharing but not sufficient (KAS runs here\n"
        "# yet is excluded from sharing until keep-aware teardown lands).\n",
        "# AcpRuntime is necessary for session sharing but not sufficient (KAS runs here\n"
        "# yet was excluded from sharing until keep-aware teardown landed — with an\n"
        "# opencode-backed KAS the teardown verb is a no-op and shared sessions stay\n"
        "# resumable, so it is now admitted).\n",
    ),
]

failures = 0
for path, old, new in EDITS:
    if old == new:
        continue
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL {path.name}: expected exactly 1 match, found {count} for: {old[:60]!r}")
        failures += 1
        continue
    backup = path.with_suffix(path.suffix + ".effortbak")
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new))
    print(f"OK   {path.name}")

sys.exit(1 if failures else 0)
