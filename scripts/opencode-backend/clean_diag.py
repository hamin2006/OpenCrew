import sys

# 1. Remove diag log from session_handle.py
p1 = "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/acp/session_handle.py"
src = open(p1).read()
old = '''                    self.last_prompt_stats.session_cost = float(_amt)
                    logger.info("DBG cost captured: %s", _amt)'''
new = '''                    self.last_prompt_stats.session_cost = float(_amt)'''
assert old in src, "session_handle diag anchor missing"
open(p1, "w").write(src.replace(old, new, 1))
print("SESSION_HANDLE CLEANED")

# 2. Remove diag log from client.py
p2 = "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/acp/client.py"
src = open(p2).read()
old = '''            import logging as _l
            _l.getLogger("kiro_crew.acp.client").info("DBG usage_update raw: %s", update)
            cost = update.get("cost")'''
new = '''            cost = update.get("cost")'''
assert old in src, "client diag anchor missing"
open(p2, "w").write(src.replace(old, new, 1))
print("CLIENT CLEANED")
