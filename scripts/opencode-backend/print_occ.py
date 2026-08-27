import re
b = open("/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/static/dist/assets/App-CBMdcfKe.js", encoding="utf-8", errors="replace").read()
for i, m in enumerate(re.finditer(r"available-models", b)):
    s = max(0, m.start() - 250)
    e = m.start() + 250
    print(f"=== OCC {i} ===")
    print(b[s:e].replace("\n", " "))
