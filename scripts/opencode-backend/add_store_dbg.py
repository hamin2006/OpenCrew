#!/usr/bin/env python3
import pathlib
p = pathlib.Path("/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/acp/session_handle.py")
t = p.read_text()
old = "        config_options = resp.get(\"configOptions\")\n        if isinstance(config_options, list):\n            self._config_options = config_options\n            self._sync_effort_levels()\n"
new = "        config_options = resp.get(\"configOptions\")\n        logger.warning(\"STORE_DBG resp_keys=%r co=%r\", list(resp.keys()), type(config_options).__name__)\n        if isinstance(config_options, list):\n            self._config_options = config_options\n            self._sync_effort_levels()\n"
assert t.count(old) == 1, t.count(old)
p.write_text(t.replace(old, new))
print("store debug added")
