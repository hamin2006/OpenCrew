// Minimal ACP probe: initialize -> session/load with a known sid -> dump.
// Usage: node acp-load-probe.js <binary> <sid> [args...]
const { spawn } = require("child_process");

const bin = process.argv[2];
const sid = process.argv[3];
const args = process.argv.slice(4);
const child = spawn(bin, args, { stdio: ["pipe", "pipe", "inherit"] });
let buf = "";
const pending = new Map();

setTimeout(() => {
  console.log("===PROBE_TIMEOUT===");
  child.kill();
  process.exit(2);
}, 45000).unref();

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
    console.log("SERVER_REQUEST", msg.method, JSON.stringify(msg.params || {}).slice(0, 200));
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result: {} }) + "\n");
    return;
  }
  if (msg.method && msg.id === undefined) return;
  const label = pending.get(msg.id) || "?";
  pending.delete(msg.id);
  if (msg.error) {
    console.log("===ERROR " + label + "===");
    console.log(JSON.stringify(msg.error, null, 1));
    child.kill();
    process.exit(1);
    return;
  }
  console.log("===RESPONSE " + label + "===");
  console.log(JSON.stringify(msg.result, null, 1));
  if (label === "initialize") {
    send({
      jsonrpc: "2.0",
      id: 2,
      method: "session/load",
      params: { sessionId: sid, cwd: process.cwd() },
    });
  } else {
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
    protocolVersion: "2025-08-22",
    clientInfo: { name: "kirocrew", version: "0.1.2" },
    clientCapabilities: {
      fs: { readTextFile: false, writeTextFile: false },
      terminal: false,
      elicitation: { form: {}, url: {} },
    },
  },
});
