// Probe: session/set_config_option effort on a live opencode session.
// Usage: node acp-config-probe.js <binary> [args...]
const { spawn } = require("child_process");

const bin = process.argv[2];
const args = process.argv.slice(3);
const child = spawn(bin, args, { stdio: ["pipe", "pipe", "inherit"] });
let buf = "";
let sid = null;
const pending = new Map();

setTimeout(() => {
  console.log("===PROBE_TIMEOUT===");
  child.kill();
  process.exit(2);
}, 90000).unref();

function send(msg) {
  pending.set(msg.id, msg.method);
  child.stdin.write(JSON.stringify(msg) + "\n");
}

function handle(line) {
  let msg;
  try {
    msg = JSON.parse(line);
  } catch {
    return;
  }
  if (msg.method && msg.id !== undefined) {
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result: {} }) + "\n");
    return;
  }
  if (msg.method && msg.id === undefined) return;
  const label = pending.get(msg.id) || "?";
  pending.delete(msg.id);
  if (msg.error) {
    console.log("===ERROR " + label + "===", JSON.stringify(msg.error).slice(0, 300));
    child.kill();
    process.exit(1);
    return;
  }
  console.log("===OK " + label + "===", JSON.stringify(Object.keys(msg.result || {})).slice(0, 150));
  if (label === "initialize") {
    send({ jsonrpc: "2.0", id: 2, method: "session/new", params: { cwd: process.cwd(), mcpServers: [] } });
  } else if (label === "session/new") {
    sid = msg.result && msg.result.sessionId;
    console.log("SESSION_ID", sid);
    send({ jsonrpc: "2.0", id: 3, method: "session/set_config_option", params: { sessionId: sid, configId: "effort", value: "low" } });
  } else if (label === "p3") {
    console.log("===DONE===");
    child.kill();
    process.exit(0);
  }
}

child.stdout.on("data", (c) => {
  buf += c.toString();
  let i;
  while ((i = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, i).trim();
    buf = buf.slice(i + 1);
    if (line) handle(line);
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
