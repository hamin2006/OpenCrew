#!/usr/bin/env python3
"""Gateway-local slash commands for the opencode backend.

opencode's ACP short-circuits unknown slash commands before the model, so
kiro-only commands were silent no-ops. Handle the useful ones from state the
gateway already tracks; /todos falls through to the model as an ordinary
prompt (opencode has a native todos tool).
"""
import pathlib
import sys

RUNNER = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_runner.py"
)

EDITS = [
    # ── 1: handler function before _handle_goal_command ──
    (
        "async def _handle_goal_command(state: \"DashboardState\", slot: \"_ChatSlot\", message: str) -> None:\n",
        "_GATEWAY_SLASH_COMMANDS = frozenset(\n"
        "    {\n"
        '        "/model",\n'
        '        "/usage",\n'
        '        "/context",\n'
        '        "/clear",\n'
        '        "/agent",\n'
        '        "/help",\n'
        '        "/changelog",\n'
        '        "/todos",\n'
        "    }\n"
        ")\n"
        "\n"
        "\n"
        "async def _handle_gateway_slash(\n"
        '    state: "DashboardState",\n'
        '    slot: "_ChatSlot",\n'
        "    session_key: str,\n"
        "    first_word: str,\n"
        "    message: str,\n"
        ") -> tuple[bool, str | None]:\n"
        '    """Answer kiro-only slash commands from gateway state.\n'
        "\n"
        "    opencode's ACP short-circuits unknown slash commands before the\n"
        "    model, so /model, /usage, /context, /clear, /agent, /help and\n"
        "    /changelog would be silent no-ops. These reply from state the\n"
        "    gateway already tracks. /todos falls through to the model as an\n"
        "    ordinary prompt (opencode has a native todos tool).\n"
        "\n"
        "    Returns (handled, rewritten_message): handled=True means the turn\n"
        "    is done; rewritten_message (with handled=False) replaces the user\n"
        "    message so the turn continues as a normal prompt.\n"
        '    """\n'
        "    _parts = message.split(None, 1)\n"
        '    _rest = _parts[1].strip() if len(_parts) > 1 else ""\n'
        "\n"
        '    if first_word == "/todos":\n'
        '        return False, f"Use your todos tool to handle: {_rest or \'show current todos\'}"\n'
        "\n"
        "    provider = state.sessions.get_provider(session_key)\n"
        '    _cur = ""\n'
        "    if provider is not None:\n"
        '        _client = getattr(provider, "_client", None)\n'
        "        if _client is not None:\n"
        '            for _opt in getattr(_client, "_config_options", None) or []:\n'
        '                if isinstance(_opt, dict) and _opt.get("id") == "model":\n'
        '                    _v = _opt.get("currentValue")\n'
        "                    if isinstance(_v, str) and _v:\n"
        "                        _cur = _v\n"
        "                    break\n"
        "            if not _cur:\n"
        '                _cur = str(getattr(_client, "_resolved_model_id", "") or "").strip()\n'
        "\n"
        '    if first_word == "/model":\n'
        "        if _cur:\n"
        '            body = f"🧠 Current model: `{_cur}`\\nSwitch it from the model picker in the chat header."\n'
        "        else:\n"
        '            body = "No active session yet — send a message first. (Or use the model picker in the header.)"\n'
        '    elif first_word == "/usage":\n'
        "        if provider is None:\n"
        '            body = "No active session yet — send a message first."\n'
        "        else:\n"
        '            _cost = provider.session_cost() if hasattr(provider, "session_cost") else None\n'
        '            _cost_txt = f"${_cost:.4f}" if isinstance(_cost, (int, float)) else "n/a"\n'
        '            _pct = provider.context_usage_pct() if hasattr(provider, "context_usage_pct") else None\n'
        '            _used = (\n'
        '                provider.context_used_tokens()\n'
        '                if hasattr(provider, "context_used_tokens")\n'
        "                else None\n"
        "            )\n"
        '            _win = (\n'
        '                provider.context_window_tokens()\n'
        '                if hasattr(provider, "context_window_tokens")\n'
        "                else None\n"
        "            )\n"
        '            body = f"💰 Session spend: {_cost_txt}"\n'
        "            if isinstance(_pct, (int, float)):\n"
        '                body += f"\\nContext: {_pct:.1f}%"\n'
        "                if (\n"
        "                    isinstance(_used, (int, float))\n"
        "                    and isinstance(_win, (int, float))\n"
        "                    and _win\n"
        "                ):\n"
        '                    body += f" ({int(_used):,} / {int(_win):,} tokens)"\n'
        '    elif first_word == "/context":\n'
        "        if provider is None:\n"
        '            body = "No active session yet — send a message first."\n'
        "        else:\n"
        '            _pct = provider.context_usage_pct() if hasattr(provider, "context_usage_pct") else None\n'
        '            _used = (\n'
        '                provider.context_used_tokens()\n'
        '                if hasattr(provider, "context_used_tokens")\n'
        "                else None\n"
        "            )\n"
        '            _win = (\n'
        '                provider.context_window_tokens()\n'
        '                if hasattr(provider, "context_window_tokens")\n'
        "                else None\n"
        "            )\n"
        "            if isinstance(_pct, (int, float)):\n"
        '                body = f"📊 Context: {_pct:.1f}%"\n'
        "                if (\n"
        "                    isinstance(_used, (int, float))\n"
        "                    and isinstance(_win, (int, float))\n"
        "                    and _win\n"
        "                ):\n"
        '                    body += f" ({int(_used):,} / {int(_win):,} tokens)"\n'
        "            else:\n"
        '                body = "Context usage not measured yet."\n'
        '    elif first_word == "/clear":\n'
        "        from kiro_crew.dashboard.chat_handlers import _reset_slot_session\n"
        "\n"
        "        await _reset_slot_session(state, slot, session_key)\n"
        '        body = "🧹 Session cleared — the next message starts fresh."\n'
        '    elif first_word == "/agent":\n'
        "        if _cur:\n"
        '            _modes: list[str] = []\n'
        '            _client = getattr(provider, "_client", None)\n'
        '            for _opt in getattr(_client, "_config_options", None) or []:\n'
        '                if isinstance(_opt, dict) and _opt.get("id") == "mode":\n'
        "                    _modes = [\n"
        '                        str(o.get("value"))\n'
        '                        for o in _opt.get("options", [])\n'
        "                        if isinstance(o, dict) and o.get(\"value\")\n"
        "                    ]\n"
        "                    break\n"
        '            body = f"🤖 Agent: `{slot.agent or \'kirocrew\'}`"\n'
        "            if _modes:\n"
        '                body += "\\nAvailable: " + ", ".join(f"`{m}`" for m in _modes)\n'
        "        else:\n"
        '            body = (\n'
        '                f"🤖 Agent: `{slot.agent or \'kirocrew\'}`\\n"\n'
        "                \"(Switch agents from the selector in the chat header.)\"\n"
        "            )\n"
        '    elif first_word == "/help":\n'
        "        body = (\n"
        "            \"Available commands:\\n\"\n"
        '            "`/compact` — compact the conversation\\n"\n'
        '            "`/model` — show the current model\\n"\n'
        '            "`/usage` — session spend + context\\n"\n'
        '            "`/context` — context usage\\n"\n'
        '            "`/clear` — start a fresh session\\n"\n'
        '            "`/agent` — current agent\\n"\n'
        '            "`/todos` — manage the task list\\n"\n'
        '            "`/changelog` — version info\\n"\n'
        '            "`/goal` — goal-driven loop\\n"\n'
        '            "`/prompts` — prompt library"\n'
        "        )\n"
        '    elif first_word == "/changelog":\n'
        "        from kiro_crew import __version__ as _kcrew_version\n"
        "\n"
        '        body = f"📦 Kiro Crew {_kcrew_version} (opencode backend)"\n'
        "    else:\n"
        "        return False, None\n"
        "\n"
        '    slot.append("assistant", body, "msg msg-a")\n'
        "    state.push_slots_update()\n"
        '    slot.append("done", "", "done")\n'
        "    return True, None\n"
        "\n"
        "\n"
        "async def _handle_goal_command(state: \"DashboardState\", slot: \"_ChatSlot\", message: str) -> None:\n",
    ),
    # ── 2: intercept block in _run_chat before the /goal block ──
    (
        "        state.push_slots_update()\n"
        '        slot.append("done", "", "done")\n'
        "        return\n"
        "\n"
        "    # ── /goal: arm / clear a goal-driven self-verdict loop (v0) ──\n",
        "        state.push_slots_update()\n"
        '        slot.append("done", "", "done")\n'
        "        return\n"
        "\n"
        "    # ── Gateway-local slash commands ──\n"
        "    # opencode's ACP short-circuits unknown slash commands before the\n"
        "    # model, so kiro-only commands would be silent no-ops; answer the\n"
        "    # useful ones from gateway state (see _handle_gateway_slash).\n"
        "    if is_slash and first_word in _GATEWAY_SLASH_COMMANDS:\n"
        "        _handled, _rewritten = await _handle_gateway_slash(\n"
        "            state, slot, session_key, first_word, message\n"
        "        )\n"
        "        if _handled:\n"
        "            return\n"
        "        if _rewritten is not None:\n"
        "            message = _rewritten\n"
        "            is_slash = False\n"
        "\n"
        "    # ── /goal: arm / clear a goal-driven self-verdict loop (v0) ──\n",
    ),
]

failures = 0
for old, new in EDITS:
    text = RUNNER.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL: expected exactly 1 match, found {count} for: {old[:60]!r}")
        failures += 1
        continue
    backup = RUNNER.with_suffix(RUNNER.suffix + ".slashbak")
    if not backup.exists():
        backup.write_text(text)
    RUNNER.write_text(text.replace(old, new))
    print("OK   chat_runner.py")

sys.exit(1 if failures else 0)
