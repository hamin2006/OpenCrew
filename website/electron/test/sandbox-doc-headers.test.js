const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { stripFrameAncestorsForSandboxDoc } = require("../sandbox-doc-headers");

describe("stripFrameAncestorsForSandboxDoc", () => {
  const sandboxUrl = "http://localhost:5476/sandbox-doc/abc123/token456";
  const otherUrl = "http://localhost:5476/api/chat";

  it("strips frame-ancestors from CSP for sandbox-doc URLs", () => {
    const headers = [
      { name: "Content-Security-Policy", value: "sandbox allow-scripts; frame-ancestors 'self'" },
      { name: "X-Content-Type-Options", value: "nosniff" },
    ];
    const result = stripFrameAncestorsForSandboxDoc(headers, sandboxUrl);
    const csp = result.find((h) => h.name === "Content-Security-Policy");
    assert.ok(csp, "CSP header must still be present");
    assert.ok(!csp.value.includes("frame-ancestors"), "frame-ancestors must be stripped");
    assert.ok(csp.value.includes("sandbox allow-scripts"), "sandbox directive must be preserved");
  });

  it("preserves all other directives in the CSP", () => {
    const headers = [
      {
        name: "Content-Security-Policy",
        value: "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox; frame-ancestors 'self'",
      },
    ];
    const result = stripFrameAncestorsForSandboxDoc(headers, sandboxUrl);
    const csp = result.find((h) => h.name === "Content-Security-Policy");
    assert.ok(csp.value.includes("sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox"));
    assert.ok(!csp.value.includes("frame-ancestors"));
  });

  it("does NOT modify headers for non-sandbox-doc URLs", () => {
    const headers = [
      { name: "Content-Security-Policy", value: "sandbox allow-scripts; frame-ancestors 'self'" },
    ];
    const result = stripFrameAncestorsForSandboxDoc(headers, otherUrl);
    const csp = result.find((h) => h.name === "Content-Security-Policy");
    assert.equal(csp.value, "sandbox allow-scripts; frame-ancestors 'self'");
  });

  it("handles URLs with /sandbox-doc/ deeper in the path (not at root)", () => {
    const headers = [
      { name: "Content-Security-Policy", value: "frame-ancestors 'self'; sandbox" },
    ];
    // /sandbox-doc/ must be at the start of the path
    const deepUrl = "http://localhost:5476/api/sandbox-doc/abc/tok";
    const result = stripFrameAncestorsForSandboxDoc(headers, deepUrl);
    const csp = result.find((h) => h.name === "Content-Security-Policy");
    assert.equal(csp.value, "frame-ancestors 'self'; sandbox", "must not modify a non-root sandbox-doc path");
  });

  it("returns the headers unchanged when URL is empty or null", () => {
    const headers = [
      { name: "Content-Security-Policy", value: "frame-ancestors 'self'" },
    ];
    assert.deepEqual(stripFrameAncestorsForSandboxDoc(headers, ""), headers);
    assert.deepEqual(stripFrameAncestorsForSandboxDoc(headers, null), headers);
    assert.deepEqual(stripFrameAncestorsForSandboxDoc(headers, undefined), headers);
  });

  it("returns an empty array when headers is null or undefined", () => {
    assert.deepEqual(stripFrameAncestorsForSandboxDoc(null, sandboxUrl), []);
    assert.deepEqual(stripFrameAncestorsForSandboxDoc(undefined, sandboxUrl), []);
  });

  it("handles an unparseable URL gracefully", () => {
    const headers = [
      { name: "Content-Security-Policy", value: "frame-ancestors 'self'" },
    ];
    const result = stripFrameAncestorsForSandboxDoc(headers, "not a url at all");
    assert.deepEqual(result, headers);
  });

  it("leaves the sandbox directive intact (security-critical)", () => {
    const headers = [
      {
        name: "Content-Security-Policy",
        value: "sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox; frame-ancestors 'self'",
      },
    ];
    const result = stripFrameAncestorsForSandboxDoc(headers, sandboxUrl);
    const csp = result.find((h) => h.name === "Content-Security-Policy");
    assert.ok(csp.value.includes("sandbox allow-scripts allow-popups allow-popups-to-escape-sandbox"));
  });

  it("handles CSP with only frame-ancestors (no other directives)", () => {
    const headers = [
      { name: "Content-Security-Policy", value: "frame-ancestors 'self'" },
    ];
    const result = stripFrameAncestorsForSandboxDoc(headers, sandboxUrl);
    const csp = result.find((h) => h.name === "Content-Security-Policy");
    assert.equal(csp.value, "", "stripping the only directive leaves an empty value");
  });

  it("preserves non-CSP headers unchanged", () => {
    const headers = [
      { name: "X-Content-Type-Options", value: "nosniff" },
      { name: "Cache-Control", value: "no-store" },
      { name: "Content-Security-Policy", value: "sandbox; frame-ancestors 'self'" },
      { name: "Referrer-Policy", value: "no-referrer" },
    ];
    const result = stripFrameAncestorsForSandboxDoc(headers, sandboxUrl);
    assert.equal(result.find((h) => h.name === "X-Content-Type-Options").value, "nosniff");
    assert.equal(result.find((h) => h.name === "Cache-Control").value, "no-store");
    assert.equal(result.find((h) => h.name === "Referrer-Policy").value, "no-referrer");
  });

  it("is case-insensitive on the CSP header name", () => {
    const headers = [
      { name: "content-security-policy", value: "sandbox; frame-ancestors 'self'" },
    ];
    const result = stripFrameAncestorsForSandboxDoc(headers, sandboxUrl);
    const csp = result.find((h) => h.name === "content-security-policy");
    assert.ok(!csp.value.includes("frame-ancestors"));
    assert.ok(csp.value.includes("sandbox"));
  });
});
