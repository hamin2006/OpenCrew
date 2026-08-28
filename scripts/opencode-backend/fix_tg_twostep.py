#!/usr/bin/env python3
"""Two-step /model picker for the opencode catalog.

The flat picker caps at 24 rows and the catalog spans 82 across 6 providers,
so step 1 posts a provider keyboard; step 2 (mp: callback) replaces it in
place with that provider's models (m: callbacks reuse the existing picker
machinery). Catalog is cached (300s TTL) so the callback doesn't re-spawn the
CLI. kiro-advertised (non-opencode) sessions keep the flat flow unchanged.
"""
import pathlib
import sys

DISPATCH = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/telegram/transport_dispatch.py"
)

EDITS = [
    # ── A: module constants ──
    (
        "# opencode binary for the /model catalog fallback (dashboard /api/models parity).\n"
        '_OPENCODE_MODELS_BIN = "/home/<user>/.opencode/bin/opencode"\n',
        "# opencode binary for the /model catalog fallback (dashboard /api/models parity).\n"
        '_OPENCODE_MODELS_BIN = "/home/<user>/.opencode/bin/opencode"\n'
        "\n"
        "# Display names for opencode provider ids in the /model pickers.\n"
        "_OPENCODE_PROVIDER_DISPLAY = {\n"
        '    "opencode": "OpenCode",\n'
        '    "opencode-go": "OpenCode Go",\n'
        '    "deepseek": "DeepSeek",\n'
        '    "openai": "OpenAI",\n'
        '    "groq": "Groq",\n'
        '    "moonshotai": "Moonshot AI",\n'
        '    "github-copilot": "GitHub Copilot",\n'
        "}\n"
        "\n"
        "# Catalog cache TTL (seconds): /model and the two-step picker refetch\n"
        "# at most once per interval — `opencode models --verbose` costs a\n"
        "# subprocess spawn.\n"
        "_OPENCODE_MODELS_CACHE_TTL = 300\n"
        "\n"
        "# Per-provider model rows in the two-step /model picker (a single\n"
        "# provider's catalog can exceed the flat picker cap; 50 rows is still\n"
        "# a scrollable list).\n"
        "_MODEL_PROVIDER_LIMIT = 50\n",
    ),
    # ── B: cache attr in __init__ ──
    (
        "        self._model_pickers: dict[str, _ModelPicker] = {}\n",
        "        self._model_pickers: dict[str, _ModelPicker] = {}\n"
        "        # Cached opencode catalog: (rows, fetched_at). The two-step\n"
        "        # /model picker resolves a provider press without re-spawning\n"
        "        # the CLI.\n"
        "        self._opencode_models_cache: tuple[list[tuple[str, str]], float] | None = None\n",
    ),
    # ── C: reuse _session_current_model in the flat fallback sort ──
    (
        "            # opencode's catalog lists providers in an order that buries\n"
        "            # everything except opencode/opencode-go under the picker cap\n"
        "            # — the session's own model can sit just past the window.\n"
        "            # Put the current model and its provider first so the picker\n"
        "            # always shows what the session is actually running.\n"
        "            cur = \"\"\n"
        "            _client = getattr(provider, \"_client\", None)\n"
        "            if _client is not None:\n"
        "                for _opt in getattr(_client, \"_config_options\", None) or []:\n"
        "                    if isinstance(_opt, dict) and _opt.get(\"id\") == \"model\":\n"
        "                        _v = _opt.get(\"currentValue\")\n"
        "                        if isinstance(_v, str) and _v:\n"
        "                            cur = _v\n"
        "                        break\n"
        "                if not cur:\n"
        "                    cur = str(getattr(_client, \"_resolved_model_id\", \"\") or \"\").strip()\n"
        "            _prov = cur.split(\"/\", 1)[0] if cur else \"\"\n",
        "            # opencode's catalog lists providers in an order that buries\n"
        "            # everything except opencode/opencode-go under the picker cap\n"
        "            # — the session's own model can sit just past the window.\n"
        "            # Put the current model and its provider first so the picker\n"
        "            # always shows what the session is actually running.\n"
        "            cur = self._session_current_model(session_key)\n"
        "            _prov = cur.split(\"/\", 1)[0] if cur else \"\"\n",
    ),
    # ── D: route to provider picker in _handle_model ──
    (
        "        session_key = self._session_key(route)\n"
        "        thread = self._route_thread(route)\n"
        "        choices = await self._model_choices(session_key)\n",
        "        session_key = self._session_key(route)\n"
        "        thread = self._route_thread(route)\n"
        "        if self._uses_opencode_catalog(session_key):\n"
        "            await self._post_provider_picker(route, chat_id, thread, session_key)\n"
        "            return\n"
        "        choices = await self._model_choices(session_key)\n",
    ),
    # ── E: new helper methods before _handle_model ──
    (
        "    async def _handle_model(self, route: tuple[str, str], chat_id: int, arg: str) -> None:\n",
        "    def _uses_opencode_catalog(self, session_key: str) -> bool:\n"
        "        \"\"\"True when /model for this session should use the two-step catalog.\n"
        "\n"
        "        opencode advertises no ``models`` payload (only configOptions), so\n"
        "        the kiro-shaped available_models() list is empty for it; the\n"
        "        catalog is the only source with real ``session/set_model`` ids.\n"
        "        \"\"\"\n"
        "        provider = self.sessions.get_provider(session_key)\n"
        "        if not str(getattr(provider, \"session_id\", \"\") or \"\").startswith(\"ses_\"):\n"
        "            return False\n"
        "        advertised = getattr(provider, \"available_models\", None)\n"
        "        if not callable(advertised):\n"
        "            return True\n"
        "        try:\n"
        "            return not [m for m in advertised() if isinstance(m, dict)]\n"
        "        except Exception:  # pragma: no cover - defensive\n"
        "            return True\n"
        "\n"
        "    def _session_current_model(self, session_key: str) -> str:\n"
        "        \"\"\"The session's current model id, or '' when unknown.\n"
        "\n"
        "        opencode reports it as the configOptions ``model`` currentValue;\n"
        "        kiro-cli as ``models.currentModelId`` (mirrored into\n"
        "        ``_resolved_model_id`` by the handle).\n"
        "        \"\"\"\n"
        "        provider = self.sessions.get_provider(session_key)\n"
        "        client = getattr(provider, \"_client\", None)\n"
        "        if client is None:\n"
        "            return \"\"\n"
        "        for opt in getattr(client, \"_config_options\", None) or []:\n"
        "            if isinstance(opt, dict) and opt.get(\"id\") == \"model\":\n"
        "                v = opt.get(\"currentValue\")\n"
        "                if isinstance(v, str) and v:\n"
        "                    return v\n"
        "                break\n"
        "        return str(getattr(client, \"_resolved_model_id\", \"\") or \"\").strip()\n"
        "\n"
        "    async def _post_provider_picker(\n"
        "        self,\n"
        "        route: tuple[str, str],\n"
        "        chat_id: int,\n"
        "        thread: int | None,\n"
        "        session_key: str,\n"
        "    ) -> None:\n"
        "        \"\"\"Step 1 of the two-step /model: post the provider keyboard.\n"
        "\n"
        "        The opencode catalog spans providers whose combined rows exceed\n"
        "        a single keyboard, so /model first asks for a provider; the\n"
        "        ``mp:`` callback then replaces this message with that provider's\n"
        "        model buttons (step 2, ``m:`` callbacks).\n"
        "        \"\"\"\n"
        "        assert self.client is not None\n"
        "        catalog = await self._fetch_opencode_model_rows()\n"
        "        if not catalog:\n"
        "            await self._reply(\n"
        "                chat_id,\n"
        "                \"⚠️ Model catalog unavailable — try again shortly.\",\n"
        "                thread=thread,\n"
        "            )\n"
        "            return\n"
        "        counts: dict[str, int] = {}\n"
        "        for mid, _label in catalog:\n"
        "            pid = mid.split(\"/\", 1)[0] if \"/\" in mid else mid\n"
        "            counts[pid] = counts.get(pid, 0) + 1\n"
        "        current = self._session_current_model(session_key)\n"
        "        rows: list[tuple[str, str]] = [(\"__auto__\", \"Auto (let the backend choose)\")]\n"
        "        rows += [\n"
        "            (pid, f\"{_OPENCODE_PROVIDER_DISPLAY.get(pid, pid)} ({counts[pid]})\")\n"
        "            for pid in sorted(counts)\n"
        "        ]\n"
        "        keyboard = [\n"
        "            [{\"text\": label, \"callback_data\": f\"mp:{pid}\"}]\n"
        "            for pid, label in rows\n"
        "        ]\n"
        "        header = f\"Current model: {current or 'Auto'}\\nPick a provider:\"\n"
        "        message_id = await self._reply(\n"
        "            chat_id,\n"
        "            header,\n"
        "            thread=thread,\n"
        "            reply_markup={\"inline_keyboard\": keyboard},\n"
        "        )\n"
        "        if message_id is None:\n"
        "            return\n"
        "        # Carry the route for the mp: callback (it edits this message).\n"
        "        self._model_pickers[f\"{chat_id}:{message_id}\"] = _ModelPicker(\n"
        "            route=route,\n"
        "            chat_id=chat_id,\n"
        "            message_id=message_id,\n"
        "            created_at=time.time(),\n"
        "            choices=(),\n"
        "        )\n"
        "        self._prune_model_pickers(time.time())\n"
        "\n"
        "    async def _handle_model(self, route: tuple[str, str], chat_id: int, arg: str) -> None:\n",
    ),
    # ── F1: cache in _fetch_opencode_model_rows ──
    (
        "        import subprocess\n"
        "\n"
        "        _PROVIDER_DISPLAY = {\n"
        '            "opencode": "OpenCode",\n'
        '            "opencode-go": "OpenCode Go",\n'
        '            "deepseek": "DeepSeek",\n'
        '            "openai": "OpenAI",\n'
        '            "groq": "Groq",\n'
        '            "moonshotai": "Moonshot AI",\n'
        '            "github-copilot": "GitHub Copilot",\n'
        "        }\n"
        "        try:\n",
        "        import subprocess\n"
        "\n"
        "        cached = self._opencode_models_cache\n"
        "        if cached is not None and time.time() - cached[1] < _OPENCODE_MODELS_CACHE_TTL:\n"
        "            return cached[0]\n"
        "        try:\n",
    ),
    # ── F2: module-level display map reference ──
    (
        "                        f\"{m.get('name') or mid} ({_PROVIDER_DISPLAY.get(pid, pid)})\",\n",
        "                        f\"{m.get('name') or mid} ({_OPENCODE_PROVIDER_DISPLAY.get(pid, pid)})\",\n",
    ),
    # ── F3: store cache before returning rows ──
    (
        "                    )\n"
        "            return rows\n"
        "        except Exception:\n"
        '            logger.warning("telegram /model: opencode models fetch failed", exc_info=True)\n'
        "            return []\n",
        "                    )\n"
        "            self._opencode_models_cache = (rows, time.time())\n"
        "            return rows\n"
        "        except Exception:\n"
        '            logger.warning("telegram /model: opencode models fetch failed", exc_info=True)\n'
        "            return []\n",
    ),
    # ── G: mp: callback handler before the m: block ──
    (
        "        # Model pick: \"m:<index>\" into the picker posted on this message.\n"
        "        if data.startswith(\"m:\"):\n",
        "        # Provider pick (two-step /model): \"mp:<provider_id>\" — replace\n"
        "        # the provider keyboard with that provider's model buttons on the\n"
        "        # SAME message (the ``m:`` handler below resolves them).\n"
        "        if data.startswith(\"mp:\"):\n"
        "            token = f\"{cb.chat_id}:{cb.message_id}\"\n"
        "            picker = self._model_pickers.get(token)\n"
        "            if picker is None or picker.choices:\n"
        "                # Pruned, or not a provider message (choices non-empty\n"
        "                # means a model list already sits on this message).\n"
        "                await self.client.edit_message(\n"
        "                    cb.chat_id,\n"
        "                    cb.message_id,\n"
        "                    \"⌛ This provider list is no longer active — send /model again.\",\n"
        "                    reply_markup={\"inline_keyboard\": []},\n"
        "                )\n"
        "                return\n"
        "            provider_id = data[3:]\n"
        "            if provider_id == \"__auto__\":\n"
        "                self._model_pickers.pop(token, None)\n"
        "                outcome = await self._apply_model(picker.route, \"\")\n"
        "                await self.client.edit_message(\n"
        "                    cb.chat_id, cb.message_id, outcome, reply_markup={\"inline_keyboard\": []}\n"
        "                )\n"
        "                return\n"
        "            catalog = await self._fetch_opencode_model_rows()\n"
        "            choices: tuple[tuple[str, str], ...] = ((\"\", \"Auto (let the backend choose)\"),) + tuple(\n"
        "                (mid, label)\n"
        "                for mid, label in catalog\n"
        "                if mid.split(\"/\", 1)[0] == provider_id\n"
        "            )[:_MODEL_PROVIDER_LIMIT]\n"
        "            if len(choices) <= 1:\n"
        "                self._model_pickers.pop(token, None)\n"
        "                await self.client.edit_message(\n"
        "                    cb.chat_id,\n"
        "                    cb.message_id,\n"
        "                    \"⚠️ No models found for that provider.\",\n"
        "                    reply_markup={\"inline_keyboard\": []},\n"
        "                )\n"
        "                return\n"
        "            # Re-register this message as a model picker with the new\n"
        "            # choices (same token — the m: handler needs no changes).\n"
        "            self._model_pickers[token] = _ModelPicker(\n"
        "                route=picker.route,\n"
        "                chat_id=cb.chat_id,\n"
        "                message_id=cb.message_id,\n"
        "                created_at=time.time(),\n"
        "                choices=choices,\n"
        "            )\n"
        "            current = self._session_current_model(self._session_key(picker.route))\n"
        "            provider_label = _OPENCODE_PROVIDER_DISPLAY.get(provider_id, provider_id)\n"
        "            header = (\n"
        "                f\"Current model: {current or 'Auto'}\\n\"\n"
        "                f\"Provider: {provider_label} — pick one:\"\n"
        "            )\n"
        "            keyboard = [\n"
        "                [\n"
        "                    {\n"
        "                        \"text\": f\"{'• ' if mid == current else ''}{label}\",\n"
        "                        \"callback_data\": f\"m:{index}\",\n"
        "                    }\n"
        "                ]\n"
        "                for index, (mid, label) in enumerate(choices)\n"
        "            ]\n"
        "            await self.client.edit_message(\n"
        "                cb.chat_id,\n"
        "                cb.message_id,\n"
        "                header,\n"
        "                reply_markup={\"inline_keyboard\": keyboard},\n"
        "            )\n"
        "            return\n"
        "\n"
        "        # Model pick: \"m:<index>\" into the picker posted on this message.\n"
        "        if data.startswith(\"m:\"):\n",
    ),
]

failures = 0
for old, new in EDITS:
    text = DISPATCH.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL: expected exactly 1 match, found {count} for: {old[:70]!r}")
        failures += 1
        continue
    backup = DISPATCH.with_suffix(DISPATCH.suffix + ".mpickbak")
    if not backup.exists():
        backup.write_text(text)
    DISPATCH.write_text(text.replace(old, new))
    print("OK   edit applied")

sys.exit(1 if failures else 0)
