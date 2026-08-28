import pathlib

p = pathlib.Path("/home/<user>/acp-models-probe.js")
t = p.read_text()
old = '      console.log("MODEL SELECT:", JSON.stringify(sel).slice(0, 2000));'
new = """      for (const o of sel.options || []) {
        if (/deepseek|opencode-go|glm-5.3|moonshotai/.test(o.value)) console.log("OPT:", o.value, "<->", o.name);
      }"""
assert old in t, "pattern missing"
p.write_text(t.replace(old, new))
print("OK")
