#!/usr/bin/env python3
"""Debug: does an opencode session handle carry configOptions?"""
import asyncio
import sys

sys.path.insert(0, "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages")

from kiro_crew.acp.client import AcpClient
from kiro_crew.acp.runtime import AcpRuntime
from kiro_crew.acp.types import ACP_BACKEND_KAS


async def main() -> None:
    client = AcpClient(agent="kirocrew", sandbox_mode="off", audit_source="subagent")
    runtime = AcpRuntime(
        work_dir=client._work_dir,
        agent="kirocrew",
        sandbox_mode="off",
        extra_env=client._extra_env or {},
        mcp_gateway_overlay=client._mcp_gateway_overlay,
        mcp_gateway_settings_mcp_json=client._mcp_gateway_settings_mcp_json,
        mcp_gateway_socket=client._mcp_gateway_socket,
        acp_backend=ACP_BACKEND_KAS,
        crew_agent=None,
    )
    await runtime.spawn()
    handle = await runtime.create_session(cwd=client._work_dir, agent="kirocrew")
    opts = handle.config_options
    print("config_options count:", len(opts))
    for opt in opts:
        if isinstance(opt, dict) and opt.get("id") in ("model", "mode"):
            print("OPT:", opt.get("id"), "| current:", opt.get("currentValue"), "| options:", len(opt.get("options", [])))
    await handle.destroy()
    await runtime.kill()


asyncio.run(main())
