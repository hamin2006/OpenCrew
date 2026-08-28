#!/usr/bin/env python3
"""Route the knowledge LLMPool through opencode on the kas backend.

AcpWorker spawns AcpClient, which can only run kiro-cli (Kiro billing). Add a
KasWorker that runs one dedicated AcpRuntime (opencode acp via the shim) with
a kirocrew-knowledge session — the same machinery the gateway's sessions use.
"""
import pathlib
import sys

POOL = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/knowledge/llm_pool.py"
)

EDITS = [
    # ── 1: imports ──
    (
        "try:\n"
        "    from kiro_crew.acp.client import AcpClient\n"
        "except ImportError:\n"
        '    AcpClient = None  # type: ignore[assignment,misc]\n',
        "try:\n"
        "    from kiro_crew.acp.client import AcpClient\n"
        "except ImportError:\n"
        '    AcpClient = None  # type: ignore[assignment,misc]\n'
        "\n"
        "try:\n"
        "    from kiro_crew.acp.runtime import AcpRuntime\n"
        "    from kiro_crew.acp.session_provider import AcpSessionProvider\n"
        "    from kiro_crew.acp.types import ACP_BACKEND_KAS\n"
        "except ImportError:\n"
        '    AcpRuntime = None  # type: ignore[assignment,misc]\n'
        '    AcpSessionProvider = None  # type: ignore[assignment,misc]\n'
        '    ACP_BACKEND_KAS = ""\n',
    ),
    # ── 2: _get_acp_backend helper after _get_provider_type ──
    (
        '    return provider if isinstance(provider, str) and provider else "acp"\n',
        '    return provider if isinstance(provider, str) and provider else "acp"\n'
        "\n"
        "\n"
        "def _get_acp_backend(config: Optional[dict] = None) -> str:\n"
        '    """Configured ACP backend ("" = kiro-cli, "kas" = KAS/opencode)."""\n'
        '    data = _read_config() if config is None else config\n'
        '    backend = _section(data, "agent").get("acp_backend", "")\n'
        "    return backend if isinstance(backend, str) and backend else \"\"\n",
    ),
    # ── 3: KasWorker class before CCWorker ──
    (
        "class CCWorker(Worker):\n",
        "class KasWorker(Worker):\n"
        '    """Long-lived opencode (kas) ACP session on a dedicated runtime.\n'
        "\n"
        "    AcpClient can only spawn kiro-cli, so on the kas backend the\n"
        "    knowledge worker is a dedicated AcpRuntime (one opencode acp\n"
        "    process) hosting one kirocrew-knowledge session — the same\n"
        "    machinery the gateway's own sessions use. The runtime owns the\n"
        "    process; shutdown() kills it.\n"
        '    """\n'
        "\n"
        "    def __init__(self, *, sandbox_mode: Optional[str] = None) -> None:\n"
        "        self._provider: Optional[AcpSessionProvider] = None\n"
        "        self._runtime: Optional[AcpRuntime] = None\n"
        "        # Config carrier only — never spawned (mirrors\n"
        "        # providers.acp._start_kiro_runtime_impl).\n"
        "        self._client: Optional[AcpClient] = None\n"
        "        self._sandbox_mode = sandbox_mode\n"
        "\n"
        "    async def start(self) -> None:\n"
        "        if self._provider is not None:\n"
        "            await self.shutdown()\n"
        "        if AcpRuntime is None or AcpSessionProvider is None:\n"
        '            raise RuntimeError("kiro_crew.acp runtime not available")\n'
        "        sandbox_mode = (\n"
        "            self._sandbox_mode\n"
        "            if self._sandbox_mode is not None\n"
        "            else await asyncio.to_thread(_get_sandbox_mode)\n"
        "        )\n"
        '        logger.info("KasWorker: starting with agent=%s", AGENT_NAME)\n'
        "        self._client = AcpClient(\n"
        '            agent=AGENT_NAME, sandbox_mode=sandbox_mode, audit_source="subagent"\n'
        "        )\n"
        "        runtime = AcpRuntime(\n"
        "            work_dir=self._client._work_dir,\n"
        '            agent=getattr(self._client, "_agent", None) or "kirocrew",\n'
        "            sandbox_mode=sandbox_mode,\n"
        '            extra_env=getattr(self._client, "_extra_env", None) or {},\n'
        '            mcp_gateway_overlay=getattr(self._client, "_mcp_gateway_overlay", None),\n'
        "            mcp_gateway_settings_mcp_json=getattr(\n"
        '                self._client, "_mcp_gateway_settings_mcp_json", None\n'
        "            ),\n"
        '            mcp_gateway_socket=getattr(self._client, "_mcp_gateway_socket", None),\n'
        "            acp_backend=ACP_BACKEND_KAS,\n"
        "            crew_agent=None,\n"
        "        )\n"
        "        await runtime.spawn()\n"
        "        handle = await runtime.create_session(\n"
        "            cwd=self._client._work_dir,\n"
        "            agent=AGENT_NAME,\n"
        "        )\n"
        "        self._runtime = runtime\n"
        "        self._provider = AcpSessionProvider(handle, runtime)\n"
        "        logger.info(\n"
        '            "KasWorker: ready (agent=%s, pid=%s)",\n'
        "            AGENT_NAME,\n"
        '            getattr(runtime, "_pid", "unknown"),\n'
        "        )\n"
        "\n"
        "    async def send_message(self, prompt: str, timeout: float = DEFAULT_TIMEOUT) -> str:\n"
        "        if self._provider is None:\n"
        "            await self.start()\n"
        "        assert self._provider is not None\n"
        "        from kiro_crew.llm_helpers import stream_and_collect\n"
        "\n"
        "        return await asyncio.wait_for(\n"
        "            stream_and_collect(self._provider, prompt), timeout=timeout\n"
        "        )\n"
        "\n"
        "    async def shutdown(self) -> None:\n"
        "        if self._provider is not None:\n"
        "            try:\n"
        "                await self._provider.shutdown()\n"
        "            except Exception:\n"
        '                logger.debug("KasWorker: session shutdown failed", exc_info=True)\n'
        "            self._provider = None\n"
        "        if self._runtime is not None:\n"
        "            try:\n"
        "                await self._runtime.kill()\n"
        "            except Exception:\n"
        '                logger.debug("KasWorker: runtime kill failed", exc_info=True)\n'
        "            self._runtime = None\n"
        "        self._client = None\n"
        "\n"
        "    def is_alive(self) -> bool:\n"
        "        return (\n"
        "            self._runtime is not None\n"
        "            and self._provider is not None\n"
        "            and self._runtime.is_alive()\n"
        "        )\n"
        "\n"
        "    def context_pct(self) -> float:\n"
        '        pct = getattr(self._provider, "context_usage_pct", None)\n'
        "        return float(pct()) if callable(pct) else 0.0\n"
        "\n"
        "    async def reset_conversation(self) -> None:\n"
        '        """Drop the accumulated transcript; fresh session on the same runtime."""\n'
        "        if self._provider is None:\n"
        "            return\n"
        "        await self._provider.new_conversation()\n"
        "\n"
        "\n"
        "class CCWorker(Worker):\n",
    ),
    # ── 4: worker selection ──
    (
        "    async def _create_worker(self) -> Worker:\n"
        '        """Create and start a new worker based on provider type."""\n'
        '        if self._provider_type == "claude_code":\n'
        "            worker: Worker = CCWorker()\n"
        "        else:\n"
        "            worker = AcpWorker(sandbox_mode=self._sandbox_mode)\n"
        "        await worker.start()\n"
        "        return worker\n",
        "    async def _create_worker(self) -> Worker:\n"
        '        """Create and start a new worker based on provider type."""\n'
        '        if self._provider_type == "claude_code":\n'
        "            worker: Worker = CCWorker()\n"
        "        elif _get_acp_backend() == ACP_BACKEND_KAS:\n"
        "            # kas (opencode) backend: AcpClient can only spawn kiro-cli,\n"
        "            # so route the worker through a dedicated AcpRuntime + session\n"
        "            # — the same path the gateway's own sessions use.\n"
        "            worker = KasWorker(sandbox_mode=self._sandbox_mode)\n"
        "        else:\n"
        "            worker = AcpWorker(sandbox_mode=self._sandbox_mode)\n"
        "        await worker.start()\n"
        "        return worker\n",
    ),
]

failures = 0
for old, new in EDITS:
    text = POOL.read_text()
    count = text.count(old)
    if count != 1:
        print(f"FAIL: expected exactly 1 match, found {count} for: {old[:60]!r}")
        failures += 1
        continue
    backup = POOL.with_suffix(POOL.suffix + ".kasbak")
    if not backup.exists():
        backup.write_text(text)
    POOL.write_text(text.replace(old, new))
    print("OK   llm_pool.py")

sys.exit(1 if failures else 0)
