import pathlib

p = pathlib.Path("/home/harsh-amin/acp-models-probe.js")
t = p.read_text()
old = 'console.log("MODEL SELECT:", JSON.stringify(opt).slice(0, 2500));'
new = 'for (const o of opt.options || []) {\n          if (/deepseek|opencode-go|glm-5.3|moonshotai/.test(o.value)) console.log("OPT:", o.value, "<-", o.name);\n        }'
assert old in t, "pattern missing"
p.write_text(t.replace(old, new))
print("OK")
