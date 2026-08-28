#!/usr/bin/env python3
"""Telegram /model: fall back to the opencode catalog when no models advertised.

opencode sessions advertise no ``models`` payload (only configOptions), so the
kiro-shaped available_models() list is empty and /model answered "No model list
available yet". Fall back to the same catalog the dashboard /api/models uses
(``opencode models --verbose``) for ses_* (opencode) sessions; its ids are the
``provider/model`` shape session/set_model accepts verbatim.
"""
import pathlib
import sys

DISPATCH = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/telegram/transport_dispatch.py"
)

EDITS = [
    # ── stdlib json import ──
    (
        "import asyncio\n"
        "import html\n"
        "import logging\n",
        "import asyncio\n"
        "import html\n"
        "import json\n"
        "import logging\n",
    ),
    # ── sandbox import (create_subprocess_limited) ──
    (
        "from kiro_crew.safety_override import describe_grant_lifetime, safety_override\n",
        "from kiro_crew.sandbox import create_subprocess_limited\n"
        "from kiro_crew.safety_override import describe_grant_lifetime, safety_override\n",
    ),
    # ── opencode binary constant ──
    (
        "_MODEL_PICKER_LIMIT = 24\n",
        "_MODEL_PICKER_LIMIT = 24\n"
        "\n"
        "# opencode binary for the /model catalog fallback (dashboard /api/models parity).\n"
        '_OPENCODE_MODELS_BIN = "/home/<user>/.opencode/bin/opencode"\n',
    ),
    # ── async signature ──
    (
        "    def _model_choices(self, session_key: str) -> tuple[tuple[str, str], ...]:\n",
        "    async def _model_choices(self, session_key: str) -> tuple[tuple[str, str], ...]:\n",
    ),
    # ── fallback + helper method ──
    (
        "        for entry in entries:\n"
        "            model_id = str(entry.get(\"modelId\") or \"\").strip()\n"
        "            # \"auto\" is already offered as the first row; listing it twice would\n"
        "            # give the same choice two buttons.\n"
        "            if not model_id or model_id == \"auto\":\n"
        "                continue\n"
        "            rows.append((model_id, str(entry.get(\"name\") or model_id)))\n"
        "        return tuple(rows[:_MODEL_PICKER_LIMIT])\n",
        "        for entry in entries:\n"
        "            model_id = str(entry.get(\"modelId\") or \"\").strip()\n"
        "            # \"auto\" is already offered as the first row; listing it twice would\n"
        "            # give the same choice two buttons.\n"
        "            if not model_id or model_id == \"auto\":\n"
        "                continue\n"
        "            rows.append((model_id, str(entry.get(\"name\") or model_id)))\n"
        "        # opencode advertises no ``models`` payload at session/new (only\n"
        "        # configOptions), so the kiro-shaped list above is empty for it.\n"
        "        # Fall back to the same catalog the dashboard /api/models uses —\n"
        "        # ``opencode models --verbose`` — whose ids are what\n"
        "        # session/set_model accepts verbatim.\n"
        "        if len(rows) <= 1 and str(getattr(provider, \"session_id\", \"\") or \"\").startswith(\"ses_\"):\n"
        "            rows = [(\"\", \"Auto (let the backend choose)\")]\n"
        "            rows.extend(await self._fetch_opencode_model_rows())\n"
        "        return tuple(rows[:_MODEL_PICKER_LIMIT])\n"
        "\n"
        "    async def _fetch_opencode_model_rows(self) -> list[tuple[str, str]]:\n"
        "        \"\"\"``(model_id, label)`` rows from ``opencode models --verbose``.\n"
        "\n"
        "        One JSON object per line; ids are ``provider/model`` — the shape\n"
        "        ``session/set_model`` accepts verbatim. Best-effort: any failure\n"
        "        degrades to an empty list (the caller keeps only the Auto row).\n"
        "        \"\"\"\n"
        "        import subprocess\n"
        "\n"
        "        _PROVIDER_DISPLAY = {\n"
        "            \"opencode\": \"OpenCode\",\n"
        "            \"opencode-go\": \"OpenCode Go\",\n"
        "            \"deepseek\": \"DeepSeek\",\n"
        "            \"openai\": \"OpenAI\",\n"
        "            \"groq\": \"Groq\",\n"
        "            \"moonshotai\": \"Moonshot AI\",\n"
        "            \"github-copilot\": \"GitHub Copilot\",\n"
        "        }\n"
        "        try:\n"
        "            proc = await create_subprocess_limited(\n"
        "                _OPENCODE_MODELS_BIN,\n"
        "                \"models\",\n"
        "                \"--verbose\",\n"
        "                stdout=subprocess.PIPE,\n"
        "                stderr=subprocess.PIPE,\n"
        "                start_new_session=True,\n"
        "            )\n"
        "            try:\n"
        "                stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=15)\n"
        "            except asyncio.TimeoutError:\n"
        "                try:\n"
        "                    proc.kill()\n"
        "                except ProcessLookupError:\n"
        "                    pass\n"
        "                await proc.communicate()\n"
        "                logger.warning(\"telegram /model: opencode models timed out\")\n"
        "                return []\n"
        "            if proc.returncode != 0 or not stdout.strip():\n"
        "                logger.warning(\"telegram /model: opencode models exited %s\", proc.returncode)\n"
        "                return []\n"
        "            rows: list[tuple[str, str]] = []\n"
        "            for line in stdout.decode(errors=\"replace\").splitlines():\n"
        "                line = line.strip()\n"
        "                if not line.startswith(\"{\"):\n"
        "                    continue\n"
        "                try:\n"
        "                    m = json.loads(line)\n"
        "                except json.JSONDecodeError:\n"
        "                    continue\n"
        "                if not isinstance(m, dict):\n"
        "                    continue\n"
        "                mid = m.get(\"id\")\n"
        "                pid = m.get(\"providerID\")\n"
        "                if not isinstance(mid, str) or not isinstance(pid, str):\n"
        "                    continue\n"
        "                rows.append(\n"
        "                    (\n"
        "                        f\"{pid}/{mid}\",\n"
        "                        f\"{m.get('name') or mid} ({_PROVIDER_DISPLAY.get(pid, pid)})\",\n"
        "                    )\n"
        "                )\n"
        "            return rows\n"
        "        except Exception:\n"
        "            logger.warning(\"telegram /model: opencode models fetch failed\", exc_info=True)\n"
        "            return []\n",
    ),
    # ── caller await ──
    (
        "        choices = self._model_choices(session_key)\n",
        "        choices = await self._model_choices(session_key)\n",
    ),
]

failures = 0
for old, new in EDITS:
    text = DISPATCH.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL: expected exactly 1 match, found {count} for: {old[:60]!r}")
        failures += 1
        continue
    backup = DISPATCH.with_suffix(DISPATCH.suffix + ".modelbak")
    if not backup.exists():
        backup.write_text(text)
    DISPATCH.write_text(text.replace(old, new))
    print("OK   transport_dispatch.py")

sys.exit(1 if failures else 0)
