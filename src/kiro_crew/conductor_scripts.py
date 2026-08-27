"""Bridge to the goal-conductor's bundled skill scripts.

The acceptance evaluator (``accept_eval.py``) and ledger entry codec
(``ledger_entry.py``) are standalone scripts that live in the skill dir.
This module exposes their entry-point functions for the MCP tool handlers in
``mcp_dashboard.py``, loading them once by file location at import time.

The scripts remain the canonical implementation and continue to work as CLI
scripts invoked via ``execute_bash``; this module simply lets the MCP layer
call into them without subprocess overhead.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Tuple

_SKILL_DIR = Path(__file__).parent / "builtin_skills" / "goal-conductor" / "scripts"


def _load_script(name: str, filename: str) -> ModuleType:
    """Load a skill script by file path without writing bytecode."""
    path = _SKILL_DIR / filename
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    prev = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = prev
    return module


# Lazy-loaded module references (populated on first call).
_accept_eval: ModuleType | None = None
_ledger_entry: ModuleType | None = None


def _get_accept_eval() -> ModuleType:
    global _accept_eval
    if _accept_eval is None:
        _accept_eval = _load_script("_conductor_accept_eval", "accept_eval.py")
    return _accept_eval


def _get_ledger_entry() -> ModuleType:
    global _ledger_entry
    if _ledger_entry is None:
        _ledger_entry = _load_script("_conductor_ledger_entry", "ledger_entry.py")
    return _ledger_entry


def evaluate_item(item: Dict[str, Any]) -> Tuple[str, str]:
    """Evaluate one work item's acceptance condition.

    Delegates to ``accept_eval._evaluate(item)`` which returns
    ``(verdict, evidence)``.
    """
    mod = _get_accept_eval()
    return mod._evaluate(item)


def ledger_mode(mode: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run a ledger codec operation.

    ``mode`` is one of: encode, decode, validate, rotate.
    Delegates to the corresponding function in ``ledger_entry._MODES``.
    """
    mod = _get_ledger_entry()
    handler = mod._MODES.get(mode)
    if handler is None:
        return {"ok": False, "error": {"code": "unknown_mode", "detail": f"unknown mode {mode!r}"}}
    return handler(payload)
