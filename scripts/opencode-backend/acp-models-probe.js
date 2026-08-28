// Dump opencode ACP session/new: models field, availableModels, model select.
const { spawn } = require("child_process");
const child = spawn(process.argv[2] || "/home/<user>/.opencode/bin/opencode", ["acp"], {
  stdio: ["pipe", "pipe", "inherit"],
});
let buf = "";
const pending = new Map();
setTimeout(() => { console.log("TIMEOUT"); child.kill(); process.exit(2); }, 90000).unref();

function send(msg) {
  pending.set(msg.id, msg.method);
  child.stdin.write(JSON.stringify(msg) + "\n");
}

child.stdout.on("data", (c) => {
  buf += c.toString();
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch { continue; }
    if (msg.method && msg.id !== undefined) {
      child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result: {} }) + "\n");
      continue;
    }
    if (msg.method && msg.id === undefined) continue;
    const label = pending.get(msg.id) || "?";
    pending.delete(msg.id);
    if (msg.error) { console.log("ERR", JSON.stringify(msg.error).slice(0, 300)); child.kill(); process.exit(1); }
    if (label === "initialize") {
      send({ jsonrpc: "2.0", id: 2, method: "session/new", params: { cwd: process.cwd(), mcpServers: [] } });
    } else if (label === "session/new") {
      const r = msg.result || {};
      console.log("RESULT KEYS:", Object.keys(r).join(","));
      console.log("models:", JSON.stringify(r.models).slice(0, 2500));
      console.log("availableModels:", JSON.stringify(r.availableModels).slice(0, 2500));
      for (const opt of r.configOptions || []) {
        if (opt.key === "model" || opt.id === "model") {
          console.log("MODEL SELECT:", JSON.stringify(opt).slice(0, 2500));
        }
      }
      child.kill();
      process.exit(0);
    }
  }
});

send({
  jsonrpc: "2.0",
  id: 0,
  method: "initialize",
  params: {
    protocolVersion: 1,
    clientInfo: { name: "kirocrew", version: "0.1.2" },
    clientCapabilities: {
      fs: { readTextFile: false, writeTextFile: false },
      terminal: false,
      elicitation: { form: {}, url: {} },
    },
  },
});
