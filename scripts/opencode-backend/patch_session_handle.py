import sys

p = "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/acp/session_handle.py"
src = open(p).read()
old = '''        if session_update == "usage_update":
            used, size = parse_usage_update(update)
            if used is not None and size:'''
new = '''        if session_update == "usage_update":
            used, size = parse_usage_update(update)
            _cost = update.get("cost")
            if isinstance(_cost, dict):
                _amt = _cost.get("amount")
                if isinstance(_amt, (int, float)) and not isinstance(_amt, bool):
                    self.last_prompt_stats.session_cost = float(_amt)
                    logger.info("DBG cost captured: %s", _amt)
            if used is not None and size:'''
assert old in src, "anchor missing"
open(p, "w").write(src.replace(old, new, 1))
print("SESSION_HANDLE PATCHED")
