// CSP header rewriting for sandbox-doc responses in the Electron shell.
//
// Why this exists: the sandbox-doc handler serves HTML artifacts and widgets
// inside an iframe. The server sets `frame-ancestors 'self'` on the response,
// which is correct when the parent page's origin exactly matches the document's
// origin. In the desktop app, however, the parent window can be loaded from
// `localhost` while the frame URL uses `127.0.0.1` (or vice versa) depending on
// how the gateway is reached. Those are distinct origins, so `frame-ancestors
// 'self'` blocks the embed and the iframe renders blank.
//
// This module strips the `frame-ancestors` directive from sandbox-doc responses
// only. The `sandbox` directive (which grants the opaque origin and is the
// security-critical control) is left intact: model-authored HTML still cannot
// access the dashboard's cookies, storage, or DOM regardless of how it is
// embedded.
//
// Pure function with no Electron dependency, so the logic is unit testable
// without a live session -- mirroring permission-handler.js.
"use strict";

/**
 * Strip `frame-ancestors` from any CSP header in the response when the
 * request URL path matches `/sandbox-doc/`.
 *
 * @param {{ name: string, value: string }[]} responseHeaders - Electron's
 *   responseHeaders array (from webRequest.onHeadersReceived details)
 * @param {string} url - the request URL
 * @returns {{ name: string, value: string }[]} - modified headers (may be the
 *   same array reference when no change is needed)
 */
function stripFrameAncestorsForSandboxDoc(responseHeaders, url) {
  if (!url || !responseHeaders) return responseHeaders || [];
  let pathname;
  try {
    pathname = new URL(url).pathname;
  } catch {
    return responseHeaders;
  }
  if (!pathname.startsWith("/sandbox-doc/")) return responseHeaders;

  return responseHeaders.map((header) => {
    const name = header.name.toLowerCase();
    if (name !== "content-security-policy") return header;
    // Remove frame-ancestors directive while preserving all others (especially
    // the sandbox directive which is security-critical).
    const stripped = header.value
      .split(";")
      .map((d) => d.trim())
      .filter((d) => !d.toLowerCase().startsWith("frame-ancestors"))
      .join("; ");
    return { name: header.name, value: stripped };
  });
}

module.exports = { stripFrameAncestorsForSandboxDoc };
