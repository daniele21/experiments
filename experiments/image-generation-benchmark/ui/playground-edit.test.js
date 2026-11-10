import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { Readable } from "node:stream";
import { deflateSync } from "node:zlib";
import test from "node:test";

import {
  classifyEditTransportFailure, editWithKorgis, getEditingAvailability,
  inspectPng, korgisOrigin, readMultipartEdit,
} from "./playground-edit.js";

function chunk(type, contents) {
  const name = Buffer.from(type, "ascii");
  const size = Buffer.alloc(4);
  size.writeUInt32BE(contents.length);
  const checksum = Buffer.alloc(4);
  // PNG CRC32 is verified in production; test fixture uses the same polynomial.
  let crc = 0xFFFFFFFF;
  for (const byte of Buffer.concat([name, contents])) {
    crc ^= byte;
    for (let i = 0; i < 8; i += 1) {
      crc = (crc >>> 1) ^ ((crc & 1) ? 0xEDB88320 : 0);
    }
  }
  checksum.writeUInt32BE((crc ^ 0xFFFFFFFF) >>> 0);
  return Buffer.concat([size, name, contents, checksum]);
}

function image(width = 512, height = 512) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  const pixels = Buffer.alloc((width * 4 + 1) * height);
  return Buffer.concat([
    Buffer.from("89504e470d0a1a0a", "hex"),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(pixels)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const MODEL = {
  key: "qwen-image-2.1-turbo-gguf-q4km",
  model_id: "qwen-image-2.1-turbo-gguf-q4km",
  runtime: "korgis-image-local",
  kind: "local",
  image_editing_supported: true,
};
const ready = () => new Response(JSON.stringify({
  data: [{ key: MODEL.key, image_editing_enabled: true }],
}), { headers: { "content-type": "application/json" } });
const notReady = () => new Response(JSON.stringify({
  data: [{ key: MODEL.key, image_editing_enabled: false }],
}), { headers: { "content-type": "application/json" } });

async function formRequest(overrides = {}) {
  const form = new FormData();
  form.set("model_key", MODEL.key);
  form.set("prompt", "Change the mug color to blue");
  form.set("image", new Blob([image()], { type: "image/png" }), "source.png");
  for (const [key, value] of Object.entries(overrides)) {
    if (value === null) form.delete(key);
    else form.set(key, value);
  }
  const input = new Request("http://localhost/edit", { method: "POST", body: form });
  const body = Buffer.from(await input.arrayBuffer());
  const stream = Readable.from([body]);
  stream.headers = {
    "content-type": input.headers.get("content-type"),
    "content-length": String(body.length),
  };
  return stream;
}

test("editing proxy permits only loopback HTTP Korgis", () => {
  assert.equal(korgisOrigin("http://127.0.0.1:1235"), "http://127.0.0.1:1235");
  assert.equal(korgisOrigin("http://localhost:1235/"), "http://localhost:1235");
  for (const url of [
    "https://example.com", "http://example.com", "http://127.0.0.1:1235/private",
    "http://user:pass@localhost:1235", "file:///etc/passwd",
  ]) {
    assert.equal(korgisOrigin(url), null);
  }
});

test("PNG validation checks dimensions and complete CRC-verified chunks", () => {
  assert.deepEqual(inspectPng(image()), { width: 512, height: 512 });
  assert.throws(() => inspectPng(Buffer.from("not a png")), /valid PNG/);
  assert.throws(() => inspectPng(image(2048, 2048)), /1 megapixel/);
  assert.throws(() => inspectPng(image().subarray(0, 50)), /incomplete PNG/);
  const corrupted = image();
  corrupted[29] ^= 0xFF;
  assert.throws(() => inspectPng(corrupted), /valid PNG/);
});

test("multipart parsing accepts one PNG and rejects arbitrary fields and sizes", async () => {
  const request = await formRequest({ seed: "42", size: "768x768", num_inference_steps: "8" });
  const result = await readMultipartEdit(request);
  assert.equal(result.model_key, MODEL.key);
  assert.equal(result.seed, 42);
  assert.equal(result.steps, 8);
  assert.equal(result.size, "768x768");
  assert.equal(result.dimensions.width, 512);
  await assert.rejects(async () => readMultipartEdit(await formRequest({ server_url: "http://evil" })), /Unexpected/);
  await assert.rejects(async () => readMultipartEdit(await formRequest({ seed: "-1" })), /Seed/);
  await assert.rejects(async () => readMultipartEdit(await formRequest({ size: "4096x4096" })), /resolution|within 1 megapixel/);
  await assert.rejects(async () => readMultipartEdit(await formRequest({ num_inference_steps: "9" })), /eight|8 inference/);
});

test("output can match a prepared portrait image at any safe 32px-aligned size", async () => {
  const result = await readMultipartEdit(await formRequest({
    size: "768x1344",
    source_original_width: "1200",
    source_original_height: "1800",
    resize_policy: "fit-1mp-grid32-canvas-high-v1",
  }));
  assert.equal(result.size, "768x1344");
  assert.equal(result.resize_policy, "fit-1mp-grid32-canvas-high-v1");
  assert.deepEqual(result.original, { width: 1200, height: 1800 });
  await assert.rejects(async () => readMultipartEdit(await formRequest({
    size: "768x1376",
  })), /within 1 megapixel/);
  await assert.rejects(async () => readMultipartEdit(await formRequest({
    resize_policy: "untrusted-code",
  })), /Unknown reference resizing policy/);
  await assert.rejects(async () => readMultipartEdit(await formRequest({
    source_original_width: "1200", source_original_height: "1800",
    resize_policy: "original",
  })), /do not match PNG/);
});

test("unavailable or unconfigured Korgis does not falsely enable editing", async () => {
  assert.equal(await getEditingAvailability(MODEL, "http://localhost:1235", async () => notReady()), false);
  assert.equal(await getEditingAvailability(MODEL, "http://localhost:1235", async () => ready()), true);
  assert.equal(await getEditingAvailability({ ...MODEL, kind: "cloud" }, "http://localhost:1235", async () => ready()), false);
});

test("one local image edit calls Korgis and persists output without original", async () => {
  const outputRoot = await fs.mkdtemp(path.join(os.tmpdir(), "imagegen-ui-edit-"));
  const input = await readMultipartEdit(await formRequest({ size: "512x512" }));
  const generated = image(512, 512);
  const calls = [];
  const mockFetch = async (url, options) => {
    calls.push([url, options]);
    assert.match(url, /127.0.0.1:1235\/v1\/models$/);
    return ready();
  };
  const mockSubmit = async (origin, form) => {
    calls.push([origin, form]);
    assert.equal(origin, "http://127.0.0.1:1235");
    assert.equal(form.get("model"), MODEL.model_id);
    assert.equal(form.get("prompt"), input.prompt);
    assert.equal(form.get("size"), "512x512");
    assert.equal(form.get("num_inference_steps"), "8");
    assert.equal(form.get("image").type, "image/png");
    return new Response(JSON.stringify({
      data: [{ b64_json: generated.toString("base64") }],
      korgis: { seed: 42, latency_ms: 165000, width: 512, height: 512 },
    }), { status: 200 });
  };
  try {
    const result = await editWithKorgis(input, {
      models: [MODEL], baseUrl: "http://127.0.0.1:1235",
      outputRoot, fetchImpl: mockFetch, submitImpl: mockSubmit,
    });
    assert.equal(calls.length, 2);
    assert.equal(result.mode, "edit");
    assert.equal(result.source_sha256, crypto.createHash("sha256").update(input.bytes).digest("hex"));
    assert.equal(result.image_url, "/api/playground/image?id=" + result.id);
    const files = await fs.readdir(path.join(outputRoot, result.id));
    assert.deepEqual(files.sort(), ["image.png", "result.json"]);
    assert.deepEqual(await fs.readFile(path.join(outputRoot, result.id, "image.png")), generated);
  } finally {
    await fs.rm(outputRoot, { recursive: true, force: true });
  }
});

test("edit aborts before generation when backend editing is disabled", async () => {
  const input = await readMultipartEdit(await formRequest());
  let calls = 0;
  await assert.rejects(() => editWithKorgis(input, {
    models: [MODEL], baseUrl: "http://127.0.0.1:1235",
    outputRoot: "/tmp/not-used",
    fetchImpl: async () => { calls += 1; return notReady(); },
  }), /--image-editing-enabled/);
  assert.equal(calls, 1);
});

test("memory rejection is explained without exposing raw provider payload", async () => {
  const input = await readMultipartEdit(await formRequest());
  await assert.rejects(() => editWithKorgis(input, {
    models: [MODEL], baseUrl: "http://127.0.0.1:1235",
    outputRoot: "/tmp/not-used",
    fetchImpl: async () => ready(),
    submitImpl: async () => new Response(JSON.stringify({ detail: {
      code: "resource_exhausted", message: "secret local details",
    } }), { status: 503 }),
  }), /memory pressure/);
});

test("transport error distinguishes timeouts from crashes and never leaks raw error text", () => {
  for (const [code, expected] of [
    ["UND_ERR_HEADERS_TIMEOUT", /response headers/],
    ["ECONNRESET", /closed during image editing/],
    ["ECONNREFUSED", /no longer listening/],
    ["ABORT_ERR", /20-minute deadline/],
  ]) {
    assert.match(classifyEditTransportFailure({ cause: { code } }), expected);
  }
  assert.doesNotMatch(
    classifyEditTransportFailure({ code: "unknown", message: "sensitive prompt contents" }),
    /sensitive prompt contents/,
  );
});

test("post-submit connection reset surfaces actionable message", async () => {
  const input = await readMultipartEdit(await formRequest());
  await assert.rejects(() => editWithKorgis(input, {
    models: [MODEL], baseUrl: "http://127.0.0.1:1235",
    outputRoot: "/tmp/not-used",
    fetchImpl: async () => ready(),
    submitImpl: async () => {
      const error = new Error("socket hang up");
      error.code = "ECONNRESET";
      throw error;
    },
  }), /Connection to Korgis closed during image editing/);
});
