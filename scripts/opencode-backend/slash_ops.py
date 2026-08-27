"""Gateway-local slash command operations for the opencode backend.

``/tools``, ``/mcp``, ``/logdump`` and ``/hooks`` are answered here because
opencode's ACP short-circuits unknown slash commands before the model ever
sees them. Each handler returns a markdown body string (and, for ``/mcp``
toggles, whether the slot session must be reset so the change takes effect);
``chat_runner._handle_gateway_slash`` wires them into the chat flow.

No kiro_crew imports: this module is pure glue over opencode's CLI, the
opencode config file, and the gateway log file.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess

_OPENCODE_BIN = "/home/harsh-amin/.opencode/bin/opencode"
_OPENCODE_CONFIG = pathlib.Path(
    os.path.expanduser("~/.config/opencode/opencode.json")
)
_SKILLS_DIR = pathlib.Path(os.path.expanduser("~/.kiro/crew/skills"))
_PLUGINS_DIR = pathlib.Path(os.path.expanduser("~/.config/opencode/plugins"))
_GATEWAY_LOG = pathlib.Path(os.path.expanduser("~/.kiro/crew/gateway.log"))

# MCP servers the gateway itself owns; disabling them breaks dashboard features.
_PROTECTED_MCPS = frozenset({"kirocrew-core", "kirocrew-cron"})

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

_BUILTIN_TOOLS = (
    ("bash", True),
    ("edit", True),
    ("write", True),
    ("read", True),
    ("grep", True),
    ("glob", True),
    ("apply_patch", True),
    ("skill", True),
    ("todowrite", True),
    ("webfetch", True),
    ("question", True),
    ("task", True),
    ("websearch", False),
    ("lsp", False),
)

_TOOL_OFF_REASONS = {
    "websearch": "needs OPENCODE_ENABLE_EXA/PARALLEL (not enabled for deepseek)",
    "lsp": "experimental, env-gated (OPENCODE_EXPERIMENTAL_LSP_TOOL)",
}

_REDACT_PATTERNS = (
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b(token|key|secret|password|bearer)\s*[=:]\s*[\"']?[^\s\"']+"),
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b"),
)


def redact(text: str) -> str:
    """Mask credentials and long opaque tokens in a log/status string."""
    out = text
    for pat in _REDACT_PATTERNS:
        out = pat.sub("[redacted]", out)
    return out


def opencode_mcp_list() -> dict | None:
    """Run ``opencode mcp list`` and parse it into ``{name: {status, reason}}``.

    Returns ``None`` when the CLI is unavailable or times out.
    """
    try:
        proc = subprocess.run(
            [_OPENCODE_BIN, "mcp", "list"],
            capture_output=True,
            text=True,
            timeout=15,
            env={
                **os.environ,
                "PATH": os.environ.get("PATH", "")
                + ":/home/harsh-amin/.local/bin",
            },
        )
        out = proc.stdout or ""
    except (subprocess.TimeoutExpired, OSError):
        return None

    servers: dict[str, dict] = {}
    current = None
    for raw in _ANSI_RE.sub("", out).splitlines():
        line = raw.strip()
        m = re.match(r"^●\s*([✓✗])\s+(\S+)\s+(connected|failed)\s*$", line)
        if m:
            servers[m.group(2)] = {"status": m.group(3), "reason": None}
            current = m.group(2)
            continue
        if current is not None and servers[current]["reason"] is None:
            if line.startswith("│") or line.startswith("|"):
                reason = line.lstrip("│| ").strip()
                if reason and not reason.startswith(("┌", "└", "╭", "╰")):
                    servers[current]["reason"] = redact(reason)[:160]
    return servers


def _mcp_config_state() -> tuple[dict, dict]:
    cfg = json.loads(_OPENCODE_CONFIG.read_text(encoding="utf-8"))
    return cfg, cfg.get("mcp", {})


def _mcp_list_body() -> str:
    cfg, mcp = _mcp_config_state()
    live = opencode_mcp_list()
    lines = [f"**MCP servers** ({len(mcp)})"]
    for name in sorted(mcp):
        entry = mcp[name]
        enabled = entry.get("enabled", True) if isinstance(entry, dict) else True
        if not enabled:
            lines.append(f"- ⏸ `{name}` — disabled")
            continue
        info = (live or {}).get(name)
        if info is None:
            lines.append(f"- · `{name}` — no status yet")
        elif info["status"] == "connected":
            lines.append(f"- ✓ `{name}` — connected")
        else:
            reason = info.get("reason")
            lines.append(f"- ✗ `{name}` — failed{f': {reason}' if reason else ''}")
    lines.append("")
    lines.append("Toggle: `/mcp <name>` — flips the config and resets this session's context.")
    lines.append("`kirocrew-core` / `kirocrew-cron` are protected (gateway-owned).")
    return "\n".join(lines)


def _toggle_mcp(name: str, enable: bool) -> tuple[str, bool]:
    cfg, mcp = _mcp_config_state()
    if name not in mcp:
        return f"Unknown MCP server: `{name}`. Run `/mcp` to see the list.", False
    entry = mcp[name]
    if not isinstance(entry, dict):
        return f"Cannot toggle `{name}` (config entry is not an object).", False
    if name in _PROTECTED_MCPS and not enable:
        return (
            f"`{name}` is owned by the gateway — disabling it would break "
            "dashboard features. Refusing."
        ), False
    backup = _OPENCODE_CONFIG.with_name(_OPENCODE_CONFIG.name + ".mcpbak")
    backup.write_text(_OPENCODE_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    entry["enabled"] = enable
    _OPENCODE_CONFIG.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    state = "on" if enable else "off"
    return (
        f"`{name}` → **{state}**. Session reset — applies on your next message "
        "(global config, all agents)."
    ), True


def handle_tools(agent: str | None = None) -> str:
    """``/tools`` — built-in tools, live MCP servers, and skill count."""
    lines = ["**Built-in tools**"]
    for name, available in _BUILTIN_TOOLS:
        if available:
            lines.append(f"- `{name}`")
        else:
            lines.append(
                f"- `{name}` — off ({_TOOL_OFF_REASONS.get(name, 'disabled')})"
            )
    if agent and agent != "kirocrew":
        lines.append(f"- _(agent `{agent}` may apply its own tool restrictions)_")
    lines.append("")
    lines.append("**MCP servers**")
    servers = opencode_mcp_list()
    if servers is None:
        lines.append("- status unavailable (`opencode mcp list` failed)")
    elif not servers:
        lines.append("- none")
    else:
        for name, info in sorted(servers.items()):
            if info["status"] == "connected":
                lines.append(f"- ✓ `{name}`")
            else:
                lines.append(f"- ✗ `{name}` — {info['reason'] or 'failed'}")
    skills = 0
    if _SKILLS_DIR.exists():
        skills = sum(
            1 for d in _SKILLS_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
        )
    lines.append("")
    lines.append(f"**Skills**: {skills} available (loaded on demand via the `skill` tool)")
    return "\n".join(lines)


def handle_mcp(rest: str) -> tuple[str, bool]:
    """``/mcp`` — list servers, or toggle one. Returns (body, needs_reset)."""
    parts = rest.split()
    if not parts:
        return _mcp_list_body(), False
    name = parts[0]
    if len(parts) > 1:
        arg = parts[1].lower()
        if arg in ("on", "enable", "true", "1"):
            enable = True
        elif arg in ("off", "disable", "false", "0"):
            enable = False
        else:
            return f"Unknown flag `{arg}` — use `on` or `off`.", False
    else:
        _, mcp = _mcp_config_state()
        if name not in mcp:
            return f"Unknown MCP server: `{name}`. Run `/mcp` to see the list.", False
        entry = mcp[name]
        enable = not (entry.get("enabled", True) if isinstance(entry, dict) else True)
    return _toggle_mcp(name, enable)


def handle_logdump(rest: str) -> str:
    """``/logdump`` — tail the gateway log with redaction."""
    n = 150
    if rest.strip():
        try:
            n = max(10, min(500, int(rest.strip().split()[0])))
        except ValueError:
            return "Usage: `/logdump` or `/logdump N` (10–500 lines)."
    if not _GATEWAY_LOG.exists():
        return "gateway.log not found."
    with open(_GATEWAY_LOG, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 65536))
        data = f.read().decode("utf-8", "replace")
    lines = data.splitlines()[-n:]
    return "```\n" + "\n".join(redact(line) for line in lines) + "\n```"


def handle_hooks() -> str:
    """``/hooks`` — inspector for opencode plugin hooks and kirocrew hooks."""
    wired = []
    if _PLUGINS_DIR.exists():
        wired = sorted(
            p.name for p in _PLUGINS_DIR.iterdir() if p.is_file() or p.is_dir()
        )
    lines = [
        "**opencode hooks** — hooks are plugin-provided "
        "(no `hooks` key exists in opencode.json).",
    ]
    if wired:
        lines.append("Plugins loaded: " + ", ".join(wired))
    else:
        lines.append(
            "Plugins loaded: none in `~/.config/opencode/plugins/`; "
            "`superpowers` (npm) provides skills only"
        )
    lines += [
        "Available events (currently unsubscribed):",
        "- **session**: created, updated, compacted, idle, error, deleted, diff, status",
        "- **tool**: execute.before, execute.after",
        "- **file**: edited, watcher.updated",
        "- **permission**: asked, replied",
        "- **other**: command.executed, todo.updated, shell.env, message.*, lsp.*, "
        "server.connected, tui.*",
        "",
        "**kirocrew hooks** — `hooks: {}` in config.json is app lifecycle hooks "
        "(on_startup/on_shutdown for apps), not user-facing.",
        "",
        "**To add one**: drop a JS plugin in `~/.config/opencode/plugins/`, e.g. "
        "`session-idle.js`:",
        "```js",
        'export const Notify = async () => ({ event: async ({ event }) => {',
        '  if (event.type === "session.idle") { /* e.g. notify Telegram */ }',
        "} })",
        "```",
    ]
    return "\n".join(lines)
