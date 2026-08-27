// ACP compaction probe: build context, send /compact, measure usage_update.
// Usage: node acp-compact-probe.js <binary> [args...]
const { spawn } = require("child_process");

const bin = process.argv[2];
const args = process.argv.slice(3);
const child = spawn(bin, args, { stdio: ["pipe", "pipe", "inherit"] });
let buf = "";
let sid = null;
const pending = new Map();
const usages = [];

setTimeout(() => {
  console.log("===PROBE_TIMEOUT===");
  child.kill();
  process.exit(2);
}, 180000).unref();

function send(msg) {
  pending.set(msg.id, msg.method);
  child.stdin.write(JSON.stringify(msg) + "\n");
}

function prompt(id, text) {
  send({
    jsonrpc: "2.0",
    id,
    method: "session/prompt",
    params: {
      sessionId: sid,
      content: [{ type: "text", text }],
    },
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
    console.log("SERVER_REQUEST", msg.method, JSON.stringify(msg.params || {}).slice(0, 200));
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: msg.id, result: {} }) + "\n");
    return;
  }
  if (msg.method === "session/update") {
    const upd = msg.params?.update || {};
    if (upd.sessionUpdate === "usage_update") {
      const ctx = upd.context || {};
      const u = { used: ctx.used, window: ctx.size, cost: upd.cost };
      usages.push(u);
      console.log("USAGE", JSON.stringify(u));
    }
    return;
  }
  if (msg.method && msg.id === undefined) return;
  const label = pending.get(msg.id) || "?";
  pending.delete(msg.id);
  if (msg.error) {
    console.log("===ERROR " + label + "===");
    console.log(JSON.stringify(msg.error).slice(0, 400));
    child.kill();
    process.exit(1);
    return;
  }
  const result = msg.result || {};
  const texts = Array.isArray(result.content)
    ? result.content.map((c) => c.text || "").join("").slice(0, 120)
    : "";
  console.log("===RESPONSE " + label + "===", JSON.stringify({ text: texts, keys: Object.keys(result) }).slice(0, 200));
  if (label === "initialize") {
    send({ jsonrpc: "2.0", id: 2, method: "session/new", params: { cwd: process.cwd(), mcpServers: [] } });
  } else if (label === "session/new") {
    sid = msg.result && msg.result.sessionId;
    console.log("SESSION_ID", sid);
    prompt(3, "Write a detailed 300-word essay about the history of the Roman Empire. Number the paragraphs.");
  } else if (label === "p3") {
    prompt(4, "Write another 300-word essay about the fall of Constantinople. Number the paragraphs.");
  } else if (label === "p4") {
    prompt(5, "/compact");
  } else if (label === "p5") {
    console.log("===COMPACT_PROMPT_DONE===");
    setTimeout(() => {
      prompt(6, "Reply with the single word: DONE");
    }, 1000);
  } else if (label === "p6") {
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
    protocolVersion: "2025-08-22",
    clientInfo: { name: "kirocrew", version: "0.1.2" },
    clientCapabilities: {
      fs: { readTextFile: false, writeTextFile: false },
      terminal: false,
      elicitation: { form: {}, url: {} },
    },
  },
});
