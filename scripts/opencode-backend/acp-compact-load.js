// Compaction on a REAL loaded session: load ses_* then /compact then measure.
// Usage: node acp-compact-load.js <binary> <sid> [args...]
const { spawn } = require("child_process");

const bin = process.argv[2];
const targetSid = process.argv[3];
const args = process.argv.slice(4);
const child = spawn(bin, args, { stdio: ["pipe", "pipe", "inherit"] });
let buf = "";
let sid = null;
const pending = new Map();
const usages = [];

setTimeout(() => {
  console.log("===PROBE_TIMEOUT===");
  child.kill();
  process.exit(2);
}, 420000).unref();

function send(msg) {
  pending.set(msg.id, msg.method);
  child.stdin.write(JSON.stringify(msg) + "\n");
}

function prompt(id, text) {
  send({
    jsonrpc: "2.0",
    id,
    method: "session/prompt",
    params: { sessionId: sid, prompt: [{ type: "text", text }] },
  });
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
  if (msg.method === "session/update") {
    const upd = msg.params?.update || {};
    if (upd.sessionUpdate === "usage_update") {
      const u = { used: upd.used, size: upd.size, cost: upd.cost };
      usages.push(u);
      console.log("USAGE", JSON.stringify(u));
    }
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
  console.log("===RESPONSE " + label + "===", JSON.stringify(Object.keys(msg.result || {})).slice(0, 160));
  if (label === "initialize") {
    send({
      jsonrpc: "2.0",
      id: 2,
      method: "session/load",
      params: { sessionId: targetSid, cwd: process.cwd() },
    });
  } else if (label === "session/load") {
    sid = targetSid;
    console.log("===LOADED===");
    prompt(3, "/compact");
  } else if (label === "p3") {
    console.log("===COMPACT_DONE===");
    setTimeout(() => {
      prompt(4, "Reply with the single word: DONE");
    }, 1500);
  } else if (label === "p4") {
    console.log("===FINAL===");
    console.log("USAGE_SUMMARY", JSON.stringify(usages, null, 1));
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
