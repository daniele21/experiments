import assert from "node:assert/strict";
import { createServer } from "node:http";
import test from "node:test";

import { EDIT_DEADLINE_MS, submitLocalEdit } from "./local-edit-transport.js";

async function withLoopbackServer(handler, fn) {
  const server = createServer(handler);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  try {
    return await fn(`http://127.0.0.1:${port}`);
  } finally {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
}

function form() {
  const result = new FormData();
  result.set("model", "qwen-image-2.1-turbo-gguf-q4km");
  result.set("prompt", "Change the color only");
  result.set("size", "512x512");
  result.set("seed", "42");
  result.set("num_inference_steps", "8");
  result.set("image", new Blob([Buffer.from("local-image-bytes")], {
    type: "image/png",
  }), "source.png");
  return result;
}

test("native local transport handles delayed response headers with no implicit fetch limit", async () => {
  await withLoopbackServer((request, response) => {
    assert.equal(request.method, "POST");
    assert.equal(request.url, "/v1/images/edits");
    assert.match(request.headers["content-type"], /multipart\/form-data; boundary=/);
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", async () => {
      const bytes = Buffer.concat(chunks);
      assert(bytes.includes(Buffer.from("local-image-bytes")));
      assert(bytes.includes(Buffer.from("Change the color only")));
      // Simulates server working before the first HTTP response header.
      await new Promise((resolve) => setTimeout(resolve, 85));
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ data: [{ b64_json: "AA==" }] }));
    });
  }, async (origin) => {
    const response = await submitLocalEdit(origin, form(), { timeoutMs: 5000 });
    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.equal(payload.data[0].b64_json, "AA==");
  });
});

test("local transport classifies sudden socket close as an error", async () => {
  await withLoopbackServer((request, response) => {
    request.resume();
    request.on("end", () => response.destroy());
  }, async (origin) => {
    await assert.rejects(
      () => submitLocalEdit(origin, form(), { timeoutMs: 3000 }),
      (error) => error.code === "ECONNRESET",
    );
  });
});

test("local transport enforces its own total editing deadline", async () => {
  await withLoopbackServer((request) => {
    request.resume(); // Deliberately never send headers.
  }, async (origin) => {
    await assert.rejects(
      () => submitLocalEdit(origin, form(), { timeoutMs: 35 }),
      (error) => error.code === "ABORT_ERR",
    );
  });
  assert.equal(EDIT_DEADLINE_MS, 20 * 60 * 1000);
});

test("local transport rejects non-loopback or unexpected multipart fields", async () => {
  await assert.rejects(
    () => submitLocalEdit("http://untrusted.example:80", form()),
    /loopback-only/,
  );
  const withUnexpected = form();
  withUnexpected.set("url", "http://untrusted.example");
  await assert.rejects(
    () => submitLocalEdit("http://127.0.0.1:1235", withUnexpected),
    /Unexpected field/,
  );
});
