p = "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/server.py"
src = open(p).read()
old = '''        show_index=False,
        append_version=True,
        max_age=0,
    )'''
new = '''        show_index=False,
        append_version=True,
    )'''
assert old in src, "revert anchor missing"
open(p, "w").write(src.replace(old, new, 1))
print("SERVER.PY REVERTED")
