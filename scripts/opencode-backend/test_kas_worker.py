#!/usr/bin/env python3
"""Smoke-test KasWorker: start -> prompt -> shutdown, on the opencode backend."""
import asyncio
import sys

sys.path.insert(0, "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages")

from kiro_crew.knowledge.llm_pool import KasWorker


async def main() -> None:
    worker = KasWorker()
    await worker.start()
    print("started, is_alive:", worker.is_alive())
    reply = await worker.send_message(
        "Reply with exactly: KNOWLEDGE_WORKER_OK", timeout=120.0
    )
    print("REPLY:", reply.strip()[:200])
    print("context_pct:", worker.context_pct())
    await worker.reset_conversation()
    print("after reset, is_alive:", worker.is_alive())
    reply2 = await worker.send_message(
        "Reply with exactly: STILL_ALIVE", timeout=120.0
    )
    print("REPLY2:", reply2.strip()[:200])
    await worker.shutdown()
    print("shutdown OK")


asyncio.run(main())
