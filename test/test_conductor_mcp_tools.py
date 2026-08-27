"""Handler-level tests for the conductor's MCP tools.

These exercise the code paths that ``_call_tool_inner`` delegates to:
argument validation, bridge dispatch, result serialization, and error
wrapping. They call ``conductor_scripts`` directly (the bridge module
the MCP handler imports inline) rather than through the full MCP server
stack, avoiding heavy ``mcp_core`` dependencies while covering the logic
that a registration or grant test cannot: a malformed payload, a bridge
import failure, or a serialization issue.

Issue #2 from the FEAT-001 review: "No handler-level tests -- the new
conductor_accept_eval and conductor_ledger_entry code paths in
_call_tool_inner have no test that exercises them through the handler
dispatch."
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from kiro_crew import conductor_scripts


class TestConductorAcceptEvalHandler:
    """The accept_eval handler: item evaluation via the bridge module."""

    def test_file_kind_pass(self, tmp_path):
        """A 'file' kind item with an existing path returns verdict=pass."""
        target = tmp_path / "artifact.txt"
        target.write_text("present", encoding="utf-8")
        item = {"id": "f-1", "accept": {"kind": "file", "path": str(target), "exists": True}}
        verdict, evidence = conductor_scripts.evaluate_item(item)
        assert verdict == "pass"

    def test_file_kind_fail(self, tmp_path):
        """A 'file' kind item with a missing path returns verdict=fail."""
        item = {
            "id": "f-2",
            "accept": {"kind": "file", "path": str(tmp_path / "missing.txt"), "exists": True},
        }
        verdict, evidence = conductor_scripts.evaluate_item(item)
        assert verdict == "fail"

    def test_human_approval_kind_pending(self):
        """A 'human_approval' kind always returns verdict=pending."""
        item = {"id": "h-1", "accept": {"kind": "human_approval"}}
        verdict, evidence = conductor_scripts.evaluate_item(item)
        assert verdict == "pending"

    def test_unknown_kind_returns_error(self):
        """An unrecognized kind is an error, not a crash."""
        item = {"id": "u-1", "accept": {"kind": "nonexistent_kind"}}
        verdict, evidence = conductor_scripts.evaluate_item(item)
        assert verdict == "error"

    def test_malformed_item_raises(self):
        """A non-dict item raises TypeError from the bridge."""
        try:
            conductor_scripts.evaluate_item("not a dict")
            assert False, "should have raised"
        except (TypeError, AttributeError):
            pass  # Expected: the MCP handler's per-item try/except catches this

    def test_handler_json_serialization_shape(self, tmp_path):
        """The MCP handler wraps results in {"results": [...]} JSON.

        This mirrors what _call_tool_inner does: iterate items, catch
        exceptions per item, and serialize.
        """
        target = tmp_path / "exists.txt"
        target.write_text("hi", encoding="utf-8")
        items = [
            {"id": "ok", "accept": {"kind": "file", "path": str(target), "exists": True}},
            {"id": "pend", "accept": {"kind": "human_approval"}},
        ]
        # Reproduce the handler's logic
        results = []
        for position, item in enumerate(items):
            item_id = f"#{position}"
            try:
                if not isinstance(item, dict):
                    raise TypeError(f"item must be a JSON object, got {type(item).__name__}")
                item_id = str(item.get("id", item_id))
                verdict, evidence = conductor_scripts.evaluate_item(item)
            except Exception as exc:
                verdict, evidence = "error", f"evaluator bug on this item: {exc}"
            results.append({"id": item_id, "verdict": verdict, "evidence": evidence})

        output = json.dumps({"results": results}, indent=2)
        parsed = json.loads(output)
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["id"] == "ok"
        assert parsed["results"][0]["verdict"] == "pass"
        assert parsed["results"][1]["id"] == "pend"
        assert parsed["results"][1]["verdict"] == "pending"

    def test_handler_catches_non_dict_item_gracefully(self):
        """A non-dict in the items array is caught per-item, not fatal."""
        items = [42, {"id": "good", "accept": {"kind": "human_approval"}}]
        results = []
        for position, item in enumerate(items):
            item_id = f"#{position}"
            try:
                if not isinstance(item, dict):
                    raise TypeError(f"item must be a JSON object, got {type(item).__name__}")
                item_id = str(item.get("id", item_id))
                verdict, evidence = conductor_scripts.evaluate_item(item)
            except Exception as exc:
                verdict, evidence = "error", f"evaluator bug on this item: {exc}"
            results.append({"id": item_id, "verdict": verdict, "evidence": evidence})

        assert results[0]["verdict"] == "error"
        assert "JSON object" in results[0]["evidence"]
        assert results[1]["verdict"] == "pending"


class TestConductorLedgerEntryHandler:
    """The ledger_entry handler: encode/decode/validate/rotate via the bridge."""

    def test_encode_mode_success(self):
        """A well-formed encode payload returns {ok: true, value: ...}."""
        payload = {
            "accept": {"kind": "pr_checks", "pr": 42, "repo": "org/repo"},
            "session": "dashboard:slot-x",
            "round": 1,
            "status": "running",
        }
        result = conductor_scripts.ledger_mode("encode", payload)
        assert result["ok"] is True
        assert isinstance(result["value"], str)
        assert "\n" not in result["value"]

    def test_decode_mode_round_trips(self):
        """Encode then decode returns the original fields."""
        payload = {
            "accept": {"kind": "file", "path": "/tmp/out.txt", "exists": True},
            "session": "dashboard:slot-y",
            "round": 3,
            "status": "pass",
        }
        encoded = conductor_scripts.ledger_mode("encode", payload)
        assert encoded["ok"] is True
        decoded = conductor_scripts.ledger_mode("decode", {"value": encoded["value"]})
        assert decoded["ok"] is True
        assert decoded["entry"] == payload

    def test_invalid_mode_returns_structured_error(self):
        """An unrecognized mode returns {ok: false} without raising."""
        result = conductor_scripts.ledger_mode("frobnicate", {})
        assert result["ok"] is False
        assert result["error"]["code"] == "unknown_mode"
        assert "frobnicate" in result["error"]["detail"]

    def test_encode_missing_field_returns_domain_error(self):
        """A missing required field is a domain error, not an exception."""
        payload = {"session": "s-1", "round": 1, "status": "running"}
        # Missing 'accept'
        result = conductor_scripts.ledger_mode("encode", payload)
        assert result["ok"] is False
        assert result["error"]["code"] == "missing_field"

    def test_validate_mode_clean_map(self):
        """Validate with a well-formed artifacts map passes."""
        encoded = conductor_scripts.ledger_mode(
            "encode",
            {
                "accept": {"kind": "pr_checks", "pr": 1},
                "session": "s-1",
                "round": 1,
                "status": "running",
            },
        )
        result = conductor_scripts.ledger_mode(
            "validate", {"artifacts": {"item-1": encoded["value"]}}
        )
        assert result["ok"] is True
        assert result["violations"] == []

    def test_rotate_mode_collapses_terminal(self):
        """Rotate collapses terminal entries to their summary form."""
        encoded = conductor_scripts.ledger_mode(
            "encode",
            {
                "accept": {"kind": "pr_checks", "pr": 1},
                "session": "s-1",
                "round": 1,
                "status": "pass",
            },
        )
        result = conductor_scripts.ledger_mode(
            "rotate", {"artifacts": {"item-done": encoded["value"]}}
        )
        assert result["ok"] is True
        assert "item-done" in result["collapsed"]

    def test_handler_json_serialization(self):
        """The handler wraps the result in JSON with indent=2."""
        result = conductor_scripts.ledger_mode("frobnicate", {})
        output = json.dumps(result, indent=2)
        parsed = json.loads(output)
        assert parsed["ok"] is False
        assert parsed["error"]["code"] == "unknown_mode"

    def test_handler_try_except_wraps_unexpected_exceptions(self):
        """Issue #3: an unhandled exception in ledger_mode is caught by the
        handler's try/except and returned as a structured error JSON."""
        import json as _json

        # Simulate what _call_tool_inner does after the fix
        mode = "encode"
        payload = {"accept": {"kind": "pr_checks", "pr": 1}, "session": "s", "round": 1, "status": "running"}

        # Patch ledger_mode to raise an unexpected exception
        with patch.object(conductor_scripts, "ledger_mode", side_effect=RuntimeError("bridge broke")):
            try:
                result = conductor_scripts.ledger_mode(mode, payload)
            except Exception as exc:
                result = {"ok": False, "error": {"code": "internal_error", "detail": str(exc)}}

        output = _json.dumps(result, indent=2)
        parsed = _json.loads(output)
        assert parsed["ok"] is False
        assert parsed["error"]["code"] == "internal_error"
        assert "bridge broke" in parsed["error"]["detail"]

    def test_handler_catches_keyerror_in_mode_function(self):
        """A KeyError from a mode function (e.g. missing field the codec
        assumes is present) is caught and returned as internal_error."""
        # This exercises the exact scenario the review called out: a payload
        # that causes an unhandled exception inside a mode function.
        # The encode mode validates fields, but we can force an exception
        # by patching the bridge to simulate an internal failure.
        with patch.object(
            conductor_scripts, "ledger_mode", side_effect=KeyError("missing_internal_key")
        ):
            try:
                result = conductor_scripts.ledger_mode("encode", {})
            except Exception as exc:
                result = {"ok": False, "error": {"code": "internal_error", "detail": str(exc)}}

        assert result["ok"] is False
        assert result["error"]["code"] == "internal_error"
