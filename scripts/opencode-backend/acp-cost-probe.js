const { spawn } = require("child_process");

const oc = spawn("/home/<user>/.opencode/bin/opencode", ["acp"], {
  stdio: ["pipe", "pipe", "inherit"],
});
let buf = "";
let sessionId = null;

function send(msg) {
  oc.stdin.write(JSON.stringify(msg) + "\n");
}

oc.stdout.on("data", (chunk) => {
  buf += chunk.toString();
  let idx;
  while ((idx = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, idx).trim();
    buf = buf.slice(idx + 1);
    if (!line) continue;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      continue;
    }
    if (msg.method === "session/update") {
      const upd = msg.params?.update || {};
      console.log("SESSION_UPDATE:", JSON.stringify(upd));
      if (upd.sessionUpdate === "usage_update") {
        console.log("USAGE_COST_FIELD:", JSON.stringify(upd.cost));
        oc.kill();
        process.exit(0);
      }
    } else if (msg.id === 2) {
      // session/new response
      sessionId = msg.result?.sessionId;
      console.log("SESSION_ID:", sessionId);
      send({
        jsonrpc: "2.0",
        id: 3,
        method: "session/prompt",
        params: { sessionId, content: [{ type: "text", text: "Reply with exactly: COST" }] },
      });
    }
  }
});

send({
  jsonrpc: "2.0",
  id: 0,
  method: "initialize",
  params: {
    protocolVersion: 1,
    clientCapabilities: { fs: { readTextFile: true, writeTextFile: true }, terminal: true },
    clientInfo: { name: "cost-probe", version: "1.0.0" },
  },
});

setTimeout(() => {
  console.log("TIMEOUT - no usage_update with cost seen");
  oc.kill();
  process.exit(1);
}, 90000);
