# opencode-backend

This branch turns Kiro Crew's ACP agent backend into **opencode** (headless,
self-hosted LLM stack) instead of kiro-cli. Tested on Linux (Ubuntu 24.04,
64-bit) and macOS, with the gateway running as a systemd service.

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
re-apply tool. Paths there are written as `/home/<user>/...` placeholders;
substitute your user before running one.

## Non-code setup (not in this repo — reproduce on a fresh machine)

All of this lives outside the package and survives any kirocrew update:

- **Frontend bundle** — `src/kiro_crew/static/dist/` is a **build artifact, not
  committed** (gitignored). After cloning the branch, restore it from a wheel:
  ```sh
  pip download --no-deps "https://download.crew.kiro.dev/cli/stable/0.3.0/kirocrew-0.3.0-py3-none-any.whl#sha256=<sha256 from SHA256SUMS>" -d /tmp/kw
  unzip -o /tmp/kw/*.whl "kiro_crew/static/*" -d /tmp/kw-x && cp -r /tmp/kw-x/kiro_crew/static ~/KiroCrew/src/kiro_crew/
  ```
  (or `make build` from the repo root). Without it the gateway serves a
  broken dashboard — `kirocrew token` prints the "stale dashboard" warning.
- **Default model** — the setup never assumes a provider: `OPENCREW_MODEL`
  overrides the default (`deepseek/deepseek-v4-flash`) for freshly created
  configs, and merging into an existing `opencode.json` keeps that config's
  own `model` for the kirocrew agents.
- **`.venv`** — the source-checkout wrapper (`~/.local/bin/kirocrew` →
  `~/KiroCrew/bin/kirocrew`) requires a bundled venv; symlink the real one:
  ```sh
  ln -sfn ~/.kiro/crew-venv ~/KiroCrew/.venv
  ```
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

## Operations

- **Backups.** The gateway ships a snapshot tool — run it nightly and keep a
  few generations:
  ```sh
  0 3 * * * ~/.kiro/crew-venv/bin/kirocrew snapshot ~/.kiro/crew-backups --keep 7
  ```
  The venv itself is re-creatable from the fork; a tar of the editable
  checkout plus `pip install -e` restores it.
- **Secrets hygiene.** Tokens live in `~/.kiro/crew/.env` (600) and opencode's
  credential store (`~/.local/share/opencode/auth.json`, 600) — never in the
  repo. The setup script writes only placeholders.
- **Updates.** `git fetch upstream && git merge upstream/main` on the checkout,
  then `sudo systemctl restart kirocrew`. Never run the official
  `cli.sh` installer.
- **Disk.** The gateway data home (`~/.kiro/crew`) can grow with session
  history and models; watch `du -sh ~/.kiro/crew` and prune old snapshots
  (the `--keep` flag handles this).

## Platform matrix

| OS | Service | Boot persistence | Notes |
|----|---------|------------------|-------|
| **Linux** | systemd (`setup.sh` + `service install`) | full — `enabled` + linger | First-class target. `Restart=on-failure`, headless-safe. |
| **macOS** | launchd (`setup.sh` + `service install`) | **login-gated** — LaunchAgents start at login | Works headless only with auto-login or a root LaunchDaemon; the gateway process env carries the KAS pins because `service_environment` propagates them at install time. |
| **Windows** | none (`setup.ps1`, experimental) | manual, or a Task Scheduler ONLOGON task | In-checkout `.venv` per stock convention; `sandbox_allow_unsandboxed_exec` must be set (stock fail-closed would refuse to run). KAS node points straight at `opencode.exe` — no shim needed. |

## kiro-cli severance

The opencode (kas) runtime has **zero kiro-cli dependency**: no boot probe, no
usage/credit scrape, no readiness gate. `kiro-cli` binaries, its state dirs
(`~/.kiro/sessions`, `~/.kiro/settings`, `~/.kiro/crew-auth-staging`) can be
deleted; the kiro backend remains only as a dormant code option. `kirocrew
doctor` reports the opencode node; the dashboard credit pill hides.

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
