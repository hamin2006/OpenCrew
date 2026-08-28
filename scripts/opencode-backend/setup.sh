#!/usr/bin/env bash
# OpenCrew setup — bootstrap a Kiro Crew gateway on the opencode (kas) backend.
#
# Idempotent: safe to re-run on an already-configured machine (it only
# creates what is missing and never clobbers existing opencode.json /
# config.json / skills without backing them up).
#
# Usage:
#   ./setup.sh            full setup (editable install, frontend, shim, env,
#                         opencode config, agents, skills, service)
#   ./setup.sh --check    verify-only: report state, change nothing
#   ./setup.sh --wheel-frontend   skip the npm build; restore static/dist from
#                         the official wheel instead
#   ./setup.sh --skip-service     do not touch systemd
#
# Requires: opencode installed (see https://opencode.ai/install), git, python3.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/hamin2006/OpenCrew.git}"
WHEEL_VERSION="${WHEEL_VERSION:-0.3.0}"
CHECKOUT="${CHECKOUT:-$HOME/KiroCrew}"
VENV="${VENV:-$HOME/.kiro/crew-venv}"
KIRO_HOME="${KIRO_HOME:-$HOME/.kiro}"
CREW_HOME="${CREW_HOME:-$KIRO_HOME/crew}"
ENV_FILE="${ENV_FILE:-/etc/kirocrew/kirocrew.env}"
OPENCODE_CONFIG="${OPENCODE_CONFIG:-$HOME/.config/opencode}"
OPENCODE_JSON="$OPENCODE_CONFIG/opencode.json"
OPENCODE_AGENT_DIR="$OPENCODE_CONFIG/agent"
SKILLS_DIR="$CREW_HOME/skills"
KIRO_AGENTS_DIR="$KIRO_HOME/agents"
OPENCODE_SKILLS_LINK="$OPENCODE_CONFIG/skills"

MODE="setup"
SKIP_SERVICE=0
WHEEL_FRONTEND=0

for arg in "$@"; do
  case "$arg" in
    --check) MODE="check" ;;
    --skip-service) SKIP_SERVICE=1 ;;
    --wheel-frontend) WHEEL_FRONTEND=1 ;;
    --help|-h)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;36m== %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  ✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31m  ✗ %s\033[0m\n' "$*"; }

# ── Preflight ──────────────────────────────────────────────────────────────
say "Preflight"
OPENCODE_BIN=""
for cand in "$HOME/.opencode/bin/opencode" "$HOME/.local/bin/opencode" /usr/local/bin/opencode; do
  if [ -x "$cand" ]; then OPENCODE_BIN="$cand"; break; fi
done
if [ -z "$OPENCODE_BIN" ]; then
  OPENCODE_BIN="$(command -v opencode || true)"
fi
if [ -z "$OPENCODE_BIN" ]; then
  fail "opencode not found. Install it first:  curl -fsSL https://opencode.ai/install | bash"
  exit 1
fi
ok "opencode: $OPENCODE_BIN"
if [ "$MODE" = "check" ]; then
  # Verify-only pass: report state of every stage.
  [ -x "$VENV/bin/kirocrew" ] && ok "crew venv: $VENV" || fail "crew venv missing: $VENV"
  [ -d "$CHECKOUT/.git" ] && ok "checkout: $CHECKOUT ($(git -C "$CHECKOUT" branch --show-current))" || fail "checkout missing: $CHECKOUT"
  [ -e "$CHECKOUT/.venv" ] && ok ".venv symlink" || fail ".venv symlink missing"
  [ -f "$CHECKOUT/src/kiro_crew/static/dist/index.html" ] && ok "frontend dist present" || fail "frontend dist missing"
  [ -f "$HOME/.local/bin/kiro-kas-shim.sh" ] && ok "kas shim present" || fail "kas shim missing"
  if [ -f "$ENV_FILE" ]; then
    grep -q "KIROCREW_KAS_NODE=" "$ENV_FILE" 2>/dev/null && ok "env file: $ENV_FILE (KIROCREW_KAS_NODE set)" || fail "env file: KIROCREW_KAS_NODE not set"
    grep -q "KIROCREW_PROJECT_DIR=" "$ENV_FILE" 2>/dev/null && ok "env file: KIROCREW_PROJECT_DIR set" || fail "env file: KIROCREW_PROJECT_DIR not set"
  else
    fail "env file missing: $ENV_FILE"
  fi
  if [ -f "$OPENCODE_JSON" ]; then
    python3 - "$OPENCODE_JSON" <<'PY' && ok "opencode.json: kirocrew agents + MCPs present" || fail "opencode.json: agents/MCPs incomplete"
import json, sys
cfg = json.load(open(sys.argv[1]))
agents = cfg.get("agent", {})
mcp = cfg.get("mcp", {})
need_agents = {"kirocrew", "kirocrew-lite", "kirocrew-research", "kirocrew-heartbeat", "kirocrew-knowledge"}
need_mcp = {"kirocrew-core", "kirocrew-cron"}
sys.exit(0 if need_agents <= set(agents) and need_mcp <= set(mcp) else 1)
PY
  else
    fail "opencode.json missing: $OPENCODE_JSON"
  fi
  for name in kirocrew-research kirocrew-heartbeat kirocrew-knowledge; do
    [ -f "$OPENCODE_AGENT_DIR/$name.md" ] && ok "agent md: $name" || fail "agent md missing: $name"
  done
  if [ -L "$OPENCODE_SKILLS_LINK" ] && [ "$(readlink "$OPENCODE_SKILLS_LINK")" = "$SKILLS_DIR" ]; then
    ok "skills symlink -> $SKILLS_DIR"
  else
    fail "skills symlink missing/incorrect"
  fi
  if systemctl is-active --quiet kirocrew 2>/dev/null; then
    ok "kirocrew.service active"
  else
    fail "kirocrew.service not active"
  fi
  say "Done. Run with no flags to apply what is missing."
  exit 0
fi

if ! command -v git >/dev/null 2>&1; then fail "git not found"; exit 1; fi
if ! command -v python3 >/dev/null 2>&1; then fail "python3 not found"; exit 1; fi
"$OPENCODE_BIN" --version >/dev/null 2>&1 && ok "opencode runs ($("$OPENCODE_BIN" --version 2>/dev/null | head -1))" || warn "opencode --version failed"

# ── 1. Crew venv (bootstrap via the official installer when missing) ───────
if [ ! -x "$VENV/bin/kirocrew" ]; then
  say "Crew venv missing — bootstrapping with the official installer"
  curl -fsSL https://download.crew.kiro.dev/cli.sh | sh
fi
ok "crew venv: $VENV"

# ── 2. Checkout ────────────────────────────────────────────────────────────
if [ -d "$CHECKOUT" ] && [ ! -d "$CHECKOUT/.git" ]; then
  fail "checkout path $CHECKOUT exists but is not a git repository"
  echo "       Move it aside or point CHECKOUT elsewhere, e.g.:"
  echo "       CHECKOUT=\$HOME/OpenCrew bash $0"
  exit 1
fi
if [ ! -d "$CHECKOUT/.git" ]; then
  say "Cloning OpenCrew"
  git clone "$REPO_URL" "$CHECKOUT"
  git -C "$CHECKOUT" remote add upstream https://github.com/kirodotdev/KiroCrew.git || true
fi
_origin="$(git -C "$CHECKOUT" remote get-url origin 2>/dev/null || true)"
case "$_origin" in
  *OpenCrew*|*KiroCrew*|*kirodotdev*|*hamin2006*) ;;
  *) warn "origin ($_origin) is not an OpenCrew/Kiro Crew remote — is this the right checkout?" ;;
esac
ok "checkout: $CHECKOUT ($(git -C "$CHECKOUT" branch --show-current))"

# ── 3. Editable install + .venv symlink ────────────────────────────────────
say "Editable install"
"$VENV/bin/pip" install -e "$CHECKOUT" >/dev/null
ln -sfn "$VENV" "$CHECKOUT/.venv"
"$VENV/bin/python" -c "import kiro_crew; assert kiro_crew.__file__.startswith('$CHECKOUT'), kiro_crew.__file__" && ok "kiro_crew resolves from the checkout" || { fail "editable install not effective"; exit 1; }

# ── 4. Frontend bundle ─────────────────────────────────────────────────────
if [ -f "$CHECKOUT/src/kiro_crew/static/dist/index.html" ]; then
  ok "frontend dist already present"
elif [ "$WHEEL_FRONTEND" = "1" ]; then
  say "Restoring frontend dist from the official wheel"
  pip download --no-deps --dest /tmp/kc-wheel "https://download.crew.kiro.dev/cli/stable/$WHEEL_VERSION/kirocrew-$WHEEL_VERSION-py3-none-any.whl#sha256=$(curl -fsSL "https://download.crew.kiro.dev/cli/stable/$WHEEL_VERSION/SHA256SUMS" | awk -v w="kirocrew-$WHEEL_VERSION-py3-none-any.whl" '$2==w{print $1}')" 2>/dev/null || { fail "wheel restore failed — run: cd $CHECKOUT && make frontend"; exit 1; }
  unzip -o -q /tmp/kc-wheel/*.whl "kiro_crew/static/*" -d /tmp/kc-wheel-x
  cp -r /tmp/kc-wheel-x/kiro_crew/static "$CHECKOUT/src/kiro_crew/"
  ok "frontend dist restored from wheel"
else
  say "Building frontend (npm/vite) — this takes a few minutes"
  if (cd "$CHECKOUT" && make frontend); then
    ok "frontend built"
  else
    warn "npm build failed — falling back to the wheel restore"
    WHEEL_FRONTEND=1
    # recurse into the restore path without re-entering this branch
    rm -rf "$CHECKOUT/src/kiro_crew/static/dist"
    pip download --no-deps --dest /tmp/kc-wheel "https://download.crew.kiro.dev/cli/stable/$WHEEL_VERSION/kirocrew-$WHEEL_VERSION-py3-none-any.whl#sha256=$(curl -fsSL "https://download.crew.kiro.dev/cli/stable/$WHEEL_VERSION/SHA256SUMS" | awk -v w="kirocrew-$WHEEL_VERSION-py3-none-any.whl" '$2==w{print $1}')" 2>/dev/null || { fail "wheel restore failed too — run manually: cd $CHECKOUT && make frontend"; exit 1; }
    unzip -o -q /tmp/kc-wheel/*.whl "kiro_crew/static/*" -d /tmp/kc-wheel-x
    cp -r /tmp/kc-wheel-x/kiro_crew/static "$CHECKOUT/src/kiro_crew/"
    ok "frontend dist restored from wheel"
  fi
fi

# ── 5. KAS shim ────────────────────────────────────────────────────────────
say "KAS shim"
SHIM="$HOME/.local/bin/kiro-kas-shim.sh"
mkdir -p "$HOME/.local/bin"
printf '#!/bin/bash\n# OpenCrew: run opencode as the KAS node.\nexec %s acp\n' "$OPENCODE_BIN" > "$SHIM"
chmod +x "$SHIM"
ok "shim: $SHIM -> $OPENCODE_BIN acp"

# ── 6. Service env file ────────────────────────────────────────────────────
say "Service env ($ENV_FILE)"
if [ -f "$ENV_FILE" ]; then
  existing=1
else
  existing=0
  if [ "$SKIP_SERVICE" = "1" ]; then
    warn "env file missing and --skip-service — creating $HOME/.kiro/crew.env instead"
    ENV_FILE="$HOME/.kiro/crew.env"
    touch "$ENV_FILE"
  fi
fi
append_env() {
  local key="$1" val="$2"
  if ! grep -q "^${key}=" "$ENV_FILE"; then
    if [ "$existing" = "1" ]; then sudo sh -c "echo '$key=$val' >> '$ENV_FILE'"; else echo "$key=$val" >> "$ENV_FILE"; fi
  fi
}
append_env "KIROCREW_KAS_NODE" "$SHIM"
append_env "KIROCREW_KAS_SCRIPT" "/bin/true"
append_env "KIROCREW_PROJECT_DIR" "$CHECKOUT"
ok "env file has KAS_NODE / KAS_SCRIPT / PROJECT_DIR"

# ── 7. opencode.json (agents + MCP servers) ────────────────────────────────
say "opencode config ($OPENCODE_JSON)"
mkdir -p "$OPENCODE_CONFIG"
if [ ! -f "$OPENCODE_JSON" ]; then
  printf '{ "$schema": "https://opencode.ai/config.json", "model": "deepseek/deepseek-v4-flash", "permission": "allow" }\n' > "$OPENCODE_JSON"
fi
cp "$OPENCODE_JSON" "$OPENCODE_JSON.bak"
KIROCREW_BIN="$VENV/bin/kirocrew" python3 - "$OPENCODE_JSON" <<'PY'
import json, os, sys
path = sys.argv[1]
cfg = json.load(open(path))
model = "deepseek/deepseek-v4-flash"
agents = {
    "kirocrew": {"description": "Kiro Crew persistent assistant agent", "mode": "primary", "model": model},
    "kirocrew-lite": {"description": "Kiro Crew lite assistant agent", "mode": "primary", "model": model},
    "kirocrew-research": {"description": "Autonomous research worker — runs one research cycle per turn in a Research Lab campaign loop.", "mode": "primary", "model": model},
    "kirocrew-heartbeat": {"description": "Unattended polling worker — runs one HeartbeatService task per cycle with a read-only toolset.", "mode": "primary", "model": model},
    "kirocrew-knowledge": {"description": "Dedicated agent for knowledge extraction, categorization, and summarization.", "mode": "primary", "model": model},
}
mcp = {
    "kirocrew-core": {"type": "local", "command": [os.environ["KIROCREW_BIN"], "mcp-core"]},
    "kirocrew-cron": {"type": "local", "command": [os.environ["KIROCREW_BIN"], "mcp-cron"]},
}
cfg.setdefault("agent", {}).update(agents)
cfg.setdefault("mcp", {}).update(mcp)
json.dump(cfg, open(path, "w"), indent=2, ensure_ascii=False)
print("+ agents", ", ".join(sorted(agents)))
print("+ mcp", ", ".join(sorted(mcp)))
PY
ok "opencode.json updated (backup: opencode.json.bak)"

# ── 8. Agent prompts ───────────────────────────────────────────────────────
say "Agent prompts ($OPENCODE_AGENT_DIR)"
mkdir -p "$OPENCODE_AGENT_DIR"
python3 - "$KIRO_AGENTS_DIR" "$OPENCODE_AGENT_DIR" <<'PY'
import json, pathlib, sys
kiro_dir, out_dir = map(pathlib.Path, sys.argv[1:])
model = "deepseek/deepseek-v4-flash"
fallbacks = {
    "kirocrew-research": "Autonomous research worker — runs one research cycle per turn.",
    "kirocrew-heartbeat": "Unattended polling worker — runs one HeartbeatService task per cycle.",
    "kirocrew-knowledge": "Dedicated agent for knowledge extraction, categorization, and summarization.",
}
for name, fallback in fallbacks.items():
    out = out_dir / f"{name}.md"
    if out.exists():
        continue
    src = kiro_dir / f"{name}.json"
    if src.exists():
        data = json.loads(src.read_text())
        prompt = (data.get("prompt") or "").strip() or fallback
        desc = (data.get("description") or fallback).strip().replace('"', "'")
    else:
        prompt, desc = fallback, fallback
    out.write_text(f"---\ndescription: {desc}\nmode: primary\nmodel: {model}\n---\n\n{prompt}\n")
    print(f"+ {out.name} ({len(prompt)} chars)")
PY
ok "agent prompts present"

# ── 9. Skills symlink ──────────────────────────────────────────────────────
say "Skills ($SKILLS_DIR -> $OPENCODE_SKILLS_LINK)"
mkdir -p "$SKILLS_DIR"
if [ -L "$OPENCODE_SKILLS_LINK" ]; then
  if [ "$(readlink "$OPENCODE_SKILLS_LINK")" != "$SKILLS_DIR" ]; then
    rm "$OPENCODE_SKILLS_LINK"
    ln -s "$SKILLS_DIR" "$OPENCODE_SKILLS_LINK"
  fi
elif [ -e "$OPENCODE_SKILLS_LINK" ]; then
  mv "$OPENCODE_SKILLS_LINK" "$OPENCODE_SKILLS_LINK.premerge"
  ln -s "$SKILLS_DIR" "$OPENCODE_SKILLS_LINK"
  warn "pre-existing skills dir moved to skills.premerge"
else
  ln -s "$SKILLS_DIR" "$OPENCODE_SKILLS_LINK"
fi
ok "skills symlink -> $SKILLS_DIR"

# ── 10. Kiro Crew config (backend = kas) ───────────────────────────────────
say "Crew config ($CREW_HOME/config.json)"
mkdir -p "$CREW_HOME"
CONFIG="$CREW_HOME/config.json"
if [ ! -f "$CONFIG" ]; then
  printf '{ "agent": { "acp_backend": "kas" } }\n' > "$CONFIG"
fi
cp "$CONFIG" "$CONFIG.bak"
python3 - "$CONFIG" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))
agent = cfg.setdefault("agent", {})
agent["acp_backend"] = "kas"
agent.setdefault("sandbox", "off")
json.dump(cfg, open(sys.argv[1], "w"), indent=2, ensure_ascii=False)
print("+ agent.acp_backend=kas, agent.sandbox=off")
PY
ok "config.json updated (backup: config.json.bak)"

# ── 11. Service ────────────────────────────────────────────────────────────
if [ "$SKIP_SERVICE" != "1" ]; then
  say "Systemd service"
  if [ ! -f /etc/systemd/system/kirocrew.service ]; then
    "$VENV/bin/kirocrew" service install
  fi
  sudo systemctl daemon-reload 2>/dev/null || true
  sudo systemctl reset-failed kirocrew 2>/dev/null || true
  sudo systemctl restart kirocrew
  ok "kirocrew.service restarted"
fi

# ── 12. Verify ─────────────────────────────────────────────────────────────
say "Verify"
if [ "$SKIP_SERVICE" != "1" ]; then
  sleep 35
fi
"$VENV/bin/kirocrew" doctor 2>&1 | grep -E "backend:|opencode:|gateway:" || true
say "Done. Dashboard: http://localhost:5476  (kirocrew token for the URL)"
