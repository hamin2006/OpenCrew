import re
b = open(
    "/home/<user>/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/static/dist/assets/App-CBMdcfKe.js",
    encoding="utf-8",
    errors="replace",
).read()
for m in re.finditer(r"available-models", b):
    s = max(0, m.start() - 400)
    e = m.start() + 400
    seg = b[s:e]
    if "queryKey" in seg or "queryFn" in seg or "fetch(" in seg:
        print("----")
        print(seg)
