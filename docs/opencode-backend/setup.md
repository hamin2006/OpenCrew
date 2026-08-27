# opencode-backend

This branch turns Kiro Crew's ACP agent backend into **opencode** (headless,
self-hosted LLM stack) instead of kiro-cli. It is the running config of the
author's Haminator PC (Ubuntu 24.04, systemd service).

## What this branch changes (vs v0.3.0)

| File | Change |
|------|--------|
| `acp/_dispatch.py` | `resolve_opencode_wire_id()` — maps dashboard display labels to opencode `provider/model` wire ids via the configOptions model select |
| `acp/client.py` | ses_* resume skips the kiro transcript gate; configOptions-only load accepted; usage cost captured; wire-id resolution in `set_model` |
| `acp/runtime.py` | mode-select configOptions consulted for agent existence; configOptions-only load accepted |
| `acp/session_handle.py` | steer gated off for ses_*; compact marked complete for native opencode compaction; cost captured; wire-id resolution in `set_model` |
| `acp/types.py` | `session_cost` field; KAS admitted to session sharing |
| `providers/acp.py` | effort via `set_config_option`; `session_cost()`; `_is_opencode_style` |
| `dashboard/handlers/agents.py` | `/api/models` reads `opencode models --verbose` instead of kiro-cli `--list-models` |
| `dashboard/chat_handlers.py` | pick API stores display labels (frontend's offered list is label-keyed); wire-id picks normalized; cost seeded into context snapshots |
| `dashboard/chat_persistence.py` | restore-time migration of stale wire-id pins to labels |
| `dashboard/chat_runner.py` | gateway-local `/tools /mcp /logdump /hooks` handlers wired in; `/goal` references the `goal` skill |
| `dashboard/chat_utils.py` | `/tools /mcp /logdump /hooks` registered; `/issue /experiment /code /side` blocked |
| `dashboard/slash_ops.py` | **new** — the four gateway-local slash command implementations |
| `dashboard/chat_orchestrator.py` | goal injection references the `goal` skill |
| `dashboard/server.py` | `/assets/` responses never cached |
| `dashboard/state.py` | context snapshots carry `cost` for the cold-read Spent row |
| `knowledge/llm_pool.py` | `KasWorker` — dedicated opencode ACP runtime for the knowledge pool |
| `slack/gateway.py` | heartbeat agent resolves as a real opencode mode |
| `telegram/transport_dispatch.py` | two-step provider/model pickers over the opencode catalog |

`scripts/opencode-backend/` holds the original one-shot patch scripts (exact
edits applied to the 0.3.0 wheel) — kept as documentation and an emergency
re-apply tool.

## Non-code setup (not in this repo — reproduce on a fresh machine)

All of this lives outside the package and survives any kirocrew update:

- **`/etc/kirocrew/kirocrew.env`**
  ```
  KIROCREW_KAS_NODE=/home/<user>/.local/bin/kiro-kas-shim.sh
  KIROCREW_KAS_SCRIPT=/bin/true
  KIROCREW_PROJECT_DIR=/home/<user>/KiroCrew
  ```
- **`~/.local/bin/kiro-kas-shim.sh`**
  ```bash
  #!/bin/bash
  exec /home/<user>/.opencode/bin/opencode acp
  ```
- **`~/.config/opencode/opencode.json`** — model (`deepseek/deepseek-v4-flash`),
  the `kirocrew*` agents (kirocrew, kirocrew-lite, kirocrew-research,
  kirocrew-heartbeat, kirocrew-knowledge), MCP servers (chrome-devtools,
  google-workspace, notebooklm, linkedin, `kirocrew-core`, `kirocrew-cron` as
  `{type: "local", command: [...]}`), superpowers plugin, `permission: allow`
- **`~/.config/opencode/agent/kirocrew-{research,heartbeat,knowledge}.md`** —
  opencode-native agent prompts derived from `~/.kiro/agents/*.json`
- **`~/.kiro/crew/skills/`** — canonical skills dir, symlinked from
  `~/.config/opencode/skills/` so both surfaces share it (includes the `goal`
  skill)
- **`~/.kiro/crew/config.json`** — `agent.acp_backend: "kas"`,
  `agent.sandbox: "off"`, `telegram.enabled: true` + `allowed_user_ids`,
  `heartbeat.default_deliver: "dashboard"`
- **`~/.kiro/crew/.env`** — `TELEGRAM_BOT_TOKEN=...`

## Update workflow

Because `KIROCREW_PROJECT_DIR` points at this checkout, the gateway treats
itself as a **git install** (`update_self_updatable: true`) whose remote is
your fork — the official wheel can never be auto-installed over your patches.

- Pull upstream changes: `git fetch upstream && git merge upstream/main`
  (or GitHub's fork sync), then `sudo systemctl restart kirocrew`
- Your commits live in the fork — nothing wipes them
- Never run the official `curl -fsSL https://download.crew.kiro.dev/cli.sh | sh`
  installer on this machine (it would replace the venv)

## Rollback to the stock wheel

1. `sudo rm /etc/kirocrew/kirocrew.env` lines for `KIROCREW_PROJECT_DIR` (keep
   the KAS node lines)
2. Re-run the official installer pinned to 0.3.0, or restore the venv snapshot:
   `tar xzf /tmp/kc-venv-backup.tgz -C ~/.kiro/crew-venv/lib/python3.12/site-packages`
3. `sudo systemctl restart kirocrew`
