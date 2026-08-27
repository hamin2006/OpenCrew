# Opencrew — opencode-backend

Run the **Kiro Crew** dashboard and messaging channels on top of
**[opencode](https://opencode.ai)** instead of kiro-cli — a fully self-hosted
agent backend on the model stack of your choice (built and tested on DeepSeek
via the opencode provider).

> Opencrew is a fork of [kirodotdev/KiroCrew](https://github.com/kirodotdev/KiroCrew)
> whose `main` branch is this opencode backend (based on v0.3.0). Sync upstream
> changes with `git fetch upstream && git merge upstream/main`.

```
Kiro Crew gateway  ── ACP (Agent Client Protocol) ──►  opencode acp  ──►  deepseek API
  dashboard / Telegram    kiro-kas-shim.sh (exec opencode acp)          (your API key)
```

Every session, subagent, cron job, heartbeat, and knowledge worker runs as an
opencode session. Dashboard features (model picker, slash commands, cost
tracking, compaction, resume) are patched to speak opencode's dialect.

## What you get

- Dashboard + Telegram chat through opencode (`deepseek/deepseek-v4-flash`)
- Working slash commands: `/tools /mcp /logdump /hooks /model /usage /context
  /clear /compact /agent /goal /prompts /todos /help /changelog`
- Model picker with real label → wire-id resolution (no "isn't offered right
  now" mismatch), session cost on the Spent row, context snapshots
- Native opencode compaction and session resume
- Subagents, cron, heartbeat, and the knowledge pool all opencode-backed

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Linux (Ubuntu 24.04 tested)** or macOS | the author runs Ubuntu 24.04 x86_64 |
| **Python 3.12** | provided by the kirocrew installer (`~/.kiro/crew-venv`) |
| **Node.js 22+** | required by opencode |
| **opencode** | installed at `~/.opencode/bin/opencode` |
| **A model provider key** | e.g. a DeepSeek API key in opencode's auth |
| **git** | to clone this branch |

### Install opencode

```sh
curl -fsSL https://opencode.ai/install | bash
```

Authenticate the provider you want (this setup uses DeepSeek):

```sh
opencode auth login
```

Verify the catalog looks right — you should see your provider's models:

```sh
opencode models | head
```

### Install Kiro Crew (one-time bootstrap)

The official installer creates the venv, the `kirocrew` CLI on your PATH, and
the systemd service scaffolding. We then replace the stock wheel with this
fork's source:

```sh
curl -fsSL https://download.crew.kiro.dev/cli.sh | sh
```

## Getting it up and running

### 1. Clone Opencrew (main is the opencode backend)

```sh
git clone https://github.com/hamin2006/Opencrew.git ~/KiroCrew
cd ~/KiroCrew
git remote add upstream https://github.com/kirodotdev/KiroCrew.git
```

### 2. Install the fork into the crew venv (editable)

```sh
~/.kiro/crew-venv/bin/pip install -e ~/KiroCrew
ln -sfn ~/.kiro/crew-venv ~/KiroCrew/.venv   # the CLI wrapper needs a bundled venv
```

Verify the import resolves to the checkout:

```sh
~/.kiro/crew-venv/bin/python -c "import kiro_crew; print(kiro_crew.__file__)"
# /home/<user>/KiroCrew/src/kiro_crew/__init__.py
```

### 3. Restore the frontend bundle

`src/kiro_crew/static/dist/` is a build artifact (gitignored — the repo does
not commit it). Restore it from the matching stock wheel, or build it:

```sh
# from the wheel (fastest):
pip download --no-deps "https://download.crew.kiro.dev/cli/stable/0.3.0/kirocrew-0.3.0-py3-none-any.whl#sha256=<sha256 from SHA256SUMS>" -d /tmp/kw
unzip -o /tmp/kw/*.whl "kiro_crew/static/*" -d /tmp/kw-x
cp -r /tmp/kw-x/kiro_crew/static ~/KiroCrew/src/kiro_crew/
# or build from source:
#   cd ~/KiroCrew && make build
```

Without it the dashboard UI is broken (`kirocrew token` prints the "stale
dashboard" warning).

### 4. Point Kiro Crew at opencode

**Shim** — `~/.local/bin/kiro-kas-shim.sh` (must be executable):

```bash
#!/bin/bash
exec /home/<user>/.opencode/bin/opencode acp
```

**Service env** — `/etc/kirocrew/kirocrew.env` (read by the systemd unit):

```
KIROCREW_KAS_NODE=/home/<user>/.local/bin/kiro-kas-shim.sh
KIROCREW_KAS_SCRIPT=/bin/true
KIROCREW_PROJECT_DIR=/home/<user>/KiroCrew
```

### 5. Configure opencode

**`~/.config/opencode/opencode.json`** — the model, the `kirocrew*` agents, and
MCP servers. Minimal working config (the gateway's own MCP servers are
required):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "deepseek/deepseek-v4-flash",
  "permission": "allow",
  "agent": {
    "kirocrew": { "description": "Kiro Crew persistent assistant agent", "mode": "primary", "model": "deepseek/deepseek-v4-flash" },
    "kirocrew-lite": { "description": "Kiro Crew lite assistant agent", "mode": "primary", "model": "deepseek/deepseek-v4-flash" },
    "kirocrew-research": { "description": "Autonomous research worker", "mode": "primary", "model": "deepseek/deepseek-v4-flash" },
    "kirocrew-heartbeat": { "description": "Unattended polling worker", "mode": "primary", "model": "deepseek/deepseek-v4-flash" },
    "kirocrew-knowledge": { "description": "Knowledge extraction and summarization", "mode": "primary", "model": "deepseek/deepseek-v4-flash" }
  },
  "mcp": {
    "kirocrew-core": { "type": "local", "command": ["/home/<user>/.kiro/crew-venv/bin/kirocrew", "mcp-core"] },
    "kirocrew-cron": { "type": "local", "command": ["/home/<user>/.kiro/crew-venv/bin/kirocrew", "mcp-cron"] }
  }
}
```

Add any other MCP servers you want (chrome-devtools, notebooklm, etc.) — all
servers listed here become available to the agent.

**Agent prompts** — `~/.config/opencode/agent/kirocrew-{research,heartbeat,
knowledge}.md` give the specialized agents their real prompts (see
`~/.kiro/agents/*.json` in a running install).

### 6. Configure Kiro Crew

**`~/.kiro/crew/config.json`** — the important keys:

```json
{
  "agent": { "acp_backend": "kas", "sandbox": "off" },
  "telegram": { "enabled": true, "allowed_user_ids": [<your telegram id>] },
  "heartbeat": { "default_deliver": "dashboard" }
}
```

**`~/.kiro/crew/.env`** — `TELEGRAM_BOT_TOKEN=...` if you use Telegram.

### 7. Install and start the service

```sh
kirocrew service install
sudo systemctl restart kirocrew
kirocrew status
```

### 8. Verify

- Open `http://localhost:5476` — the dashboard should load and chat should
  answer through opencode
- Send `/tools` in a chat — it lists opencode's built-in tools, MCP servers,
  and the skill count
- `/mcp` shows MCP server status; `/model` shows the current model; the model
  picker in the header should switch models without "isn't offered" errors
- `kirocrew token` should print a dashboard URL without warnings

## Updating

Because `KIROCREW_PROJECT_DIR` points at this checkout, the gateway treats
itself as a git install — the official wheel can never overwrite your patches.

```sh
cd ~/KiroCrew
git fetch upstream && git merge upstream/main   # or GitHub's fork sync
git push origin opencode-backend
sudo systemctl restart kirocrew
```

## Docs

- [`docs/opencode-backend/setup.md`](setup.md) — full file-by-file change log,
  non-code setup reference, and rollback to the stock wheel
- [`scripts/opencode-backend/`](../../scripts/opencode-backend/) — the original
  one-shot patch scripts applied to the 0.3.0 wheel (documentation + emergency
  re-apply tool)
