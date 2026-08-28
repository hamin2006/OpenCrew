#!/usr/bin/env python3
"""Normalize wire-id picks to labels at the pick API (reverse catalog lookup)."""
import pathlib

PATH = pathlib.Path(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/chat_handlers.py"
)

OLD = (
    "    # opencode: slot.model stores the DISPLAY LABEL the picker sent \u2014 the\n"
    "    # frontend's \"offered\" list is label-keyed (model_name), so a wire id\n"
    "    # here would render the pin \"not offered\". Every set_model boundary\n"
    "    # resolves label -> wire id via configOptions (resolve_opencode_wire_id).\n"
)

NEW = (
    "    # opencode: slot.model stores the DISPLAY LABEL the picker sent \u2014 the\n"
    "    # frontend's \"offered\" list is label-keyed (model_name), so a wire id\n"
    "    # here would render the pin \"not offered\". Every set_model boundary\n"
    "    # resolves label -> wire id via configOptions (resolve_opencode_wire_id).\n"
    "    if model_name and model_name != \"auto\":\n"
    "        if \"/\" in model_name:\n"
    "            # A wire id came in directly (API call): store its label so the\n"
    "            # frontend still recognizes the pin. Reverse lookup over the\n"
    "            # catalog; unknown wire ids pass through unchanged.\n"
    "            for _k, _v in (await _opencode_model_catalog()).items():\n"
    "                if _v == model_name and _k != model_name and \" (\" in _k:\n"
    "                    model_name = _k\n"
    "                    break\n"
)

t = PATH.read_text(encoding="utf-8")
assert t.count(OLD) == 1, t.count(OLD)
b = PATH.with_suffix(PATH.suffix + ".normbak")
if not b.exists():
    b.write_text(t, encoding="utf-8")
PATH.write_text(t.replace(OLD, NEW), encoding="utf-8")
print("OK   wire-id normalization added")
