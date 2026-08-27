// Concurrency probe: two sessions, SIMULTANEOUS prompts on ONE acp process.
// Usage: node acp-parallel-probe.js <binary> [args...]
const { spawn } = require("child_process");

const bin = process.argv[2];
const args = process.argv.slice(3);
const child = spawn(bin, args, { stdio: ["pipe", "pipe", "inherit"] });
let buf = "";
const pending = new Map();
let s1 = null;
let s2 = null;
let alphaDone = false;
let betaDone = false;
const t0 = Date.now();

setTimeout(() => {
  console.log("===PROBE_TIMEOUT===");
  child.kill();
  process.exit(2);
}, 120000).unref();

function send(id, method, params, label) {
  pending.set(id, label);
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
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
    console.log("===ERROR " + label + "===", JSON.stringify(msg.error).slice(0, 200));
    child.kill();
    process.exit(1);
    return;
  }
  const t = ((Date.now() - t0) / 1000).toFixed(1);
  console.log("===OK " + label + " at " + t + "s===");
  if (label === "initialize") {
    send(2, "session/new", { cwd: process.cwd(), mcpServers: [] }, "new1");
  } else if (label === "new1") {
    s1 = msg.result && msg.result.sessionId;
    console.log("S1", s1);
    send(3, "session/new", { cwd: process.cwd(), mcpServers: [] }, "new2");
  } else if (label === "new2") {
    s2 = msg.result && msg.result.sessionId;
    console.log("S2", s2);
    send(4, "session/prompt", { sessionId: s1, prompt: [{ type: "text", text: "Reply with exactly: ALPHA" }] }, "p-alpha");
    send(5, "session/prompt", { sessionId: s2, prompt: [{ type: "text", text: "Reply with exactly: BETA" }] }, "p-beta");
  } else if (label === "p-alpha") {
    alphaDone = true;
    console.log("ALPHA_COMPLETED");
  } else if (label === "p-beta") {
    betaDone = true;
    console.log("BETA_COMPLETED");
  }
  if (alphaDone && betaDone) {
    console.log("===ALL_DONE===");
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

send(0, "initialize", {
  protocolVersion: 1,
  clientInfo: { name: "kirocrew", version: "0.1.2" },
  clientCapabilities: {
    fs: { readTextFile: false, writeTextFile: false },
    terminal: false,
    elicitation: { form: {}, url: {} },
  },
}, "initialize");
