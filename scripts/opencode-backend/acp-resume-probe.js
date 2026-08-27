// ACP handshake probe: initialize -> session/new -> prompt -> session/load
// Usage: node acp-resume-probe.js <binary> [args...]
// Mirrors kiro_crew's AcpClient handshake payloads.
const { spawn } = require("child_process");

const bin = process.argv[2];
const args = process.argv.slice(3);

setTimeout(() => {
  console.log("===PROBE_TIMEOUT===");
  child.kill();
  process.exit(2);
}, 90000).unref();
const child = spawn(bin, args, { stdio: ["pipe", "pipe", "inherit"] });
let buf = "";
let sid = null;
const pending = new Map();

function send(msg) {
  pending.set(msg.id, msg.method);
  child.stdin.write(JSON.stringify(msg) + "\n");
}

function show(label, obj, max = 900) {
  console.log("===" + label + "===");
  console.log(JSON.stringify(obj, null, 1).slice(0, max));
}

function handle(line) {
  let msg;
  try {
    msg = JSON.parse(line);
  } catch {
    return;
  }
  if (msg.method && msg.id !== undefined) {
    // Server-initiated request (e.g. _kiro/auth/getAccessToken) — log and
    // answer {} so the handshake can proceed.
    console.log("SERVER_REQUEST", msg.method, JSON.stringify(msg.params || {}).slice(0, 300));
    child.stdin.write(
      JSON.stringify({ jsonrpc: "2.0", id: msg.id, result: {} }) + "\n"
    );
    return;
  }
  if (msg.method && msg.id === undefined) {
    if (msg.method !== "session/update") {
      console.log("NOTIFY", msg.method, JSON.stringify(msg.params).slice(0, 300));
    }
    return;
  }
  const label = pending.get(msg.id) || "?";
  pending.delete(msg.id);
  if (msg.error) {
    show(label + " ERROR", msg.error);
    child.kill();
    process.exit(1);
    return;
  }
  show(label, msg.result);
  if (label === "initialize") {
    send({
      jsonrpc: "2.0",
      id: 2,
      method: "session/new",
      params: { cwd: process.cwd(), mcpServers: [] },
    });
  } else if (label === "session/new") {
    sid = msg.result && msg.result.sessionId;
    send({
      jsonrpc: "2.0",
      id: 3,
      method: "session/prompt",
      params: {
        sessionId: sid,
        content: [{ type: "text", text: "Reply with exactly: COST" }],
      },
    });
  } else if (label === "session/prompt") {    setTimeout(() => {
      send({
        jsonrpc: "2.0",
        id: 4,
        method: "session/load",
        params: { sessionId: sid, cwd: process.cwd() },
      });
    }, 500);
  } else if (label === "session/load") {
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
