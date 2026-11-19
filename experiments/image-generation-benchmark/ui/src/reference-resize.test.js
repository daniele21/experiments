import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_ORIGINAL_PIXELS,
  MAX_PREPARED_PIXELS,
  RESIZE_POLICY,
  chooseReferenceSize,
  matchedOutputSize,
  prepareReferenceImage,
  readReferenceHeader,
} from "./reference-resize.js";

function pngHeader(width, height) {
  const bytes = Buffer.alloc(33);
  Buffer.from("89504e470d0a1a0a", "hex").copy(bytes, 0);
  bytes.writeUInt32BE(13, 8);
  bytes.write("IHDR", 12, "ascii");
  bytes.writeUInt32BE(width, 16);
  bytes.writeUInt32BE(height, 20);
  bytes[24] = 8;
  bytes[25] = 6;
  return bytes;
}

test("large portrait infographic deterministically fits within 1 MP without cropping", () => {
  const plan = chooseReferenceSize(1200, 1800);
  assert.equal(plan.resized, true);
  assert.equal(plan.policy, RESIZE_POLICY);
  assert.equal(plan.width % 32, 0);
  assert.equal(plan.height % 32, 0);
  assert(plan.width * plan.height <= MAX_PREPARED_PIXELS);
  assert(plan.width < 1200 && plan.height < 1800);
  assert(Math.abs(plan.width / plan.height - 1200 / 1800) < 0.03);
  assert.deepEqual(plan, chooseReferenceSize(1200, 1800));
  assert.equal(matchedOutputSize(plan.width, plan.height), `${plan.width}x${plan.height}`);
});

test("square and landscape sources get repeatable bounded dimensions", () => {
  for (const [w, h] of [[1600, 1600], [4032, 3024], [8192, 2048]]) {
    const a = chooseReferenceSize(w, h);
    assert(a.width * a.height <= MAX_PREPARED_PIXELS);
    assert(a.width <= 2048 && a.height <= 2048);
    assert(a.width <= w && a.height <= h);
    assert.equal(a.width % 32, 0);
    assert.equal(a.height % 32, 0);
    assert.deepEqual(a, chooseReferenceSize(w, h));
  }
});

test("small compatible sources remain pixel-identical, never upscaled or re-encoded", () => {
  assert.deepEqual(
    chooseReferenceSize(752, 768),
    { width: 752, height: 768, resized: false, policy: "original" },
  );
  assert.equal(matchedOutputSize(752, 768), "736x768");
});

test("malicious or ultra-narrow images fail before decode", () => {
  for (const dims of [[0, 1024], [25, 512], [6000, 6000], [100000, 12], [32, 16384]]) {
    assert.throws(() => chooseReferenceSize(...dims), /unsupported|too narrow/);
  }
  assert(MAX_ORIGINAL_PIXELS > MAX_PREPARED_PIXELS);
});

test("input header checks PNG format, size and source dimensions", async () => {
  const file = new File([pngHeader(1200, 1800)], "graphic.png", { type: "image/png" });
  assert.deepEqual(await readReferenceHeader(file), { width: 1200, height: 1800 });
  await assert.rejects(() => readReferenceHeader(
    new File([Buffer.from("not png")], "graphic.png", { type: "image/png" }),
  ), /not a valid PNG/);
  await assert.rejects(() => readReferenceHeader(
    new File([pngHeader(6000, 6000)], "huge.png", { type: "image/png" }),
  ), /unsupported/);
});

test("browser preprocessing uses a fixed canvas scale and preserves original separately", async () => {
  const original = new File([pngHeader(1200, 1800)], "graphic.png", { type: "image/png" });
  const oldBitmap = globalThis.createImageBitmap;
  const oldDocument = globalThis.document;
  let closed = false;
  let drawing;
  const canvas = {
    width: 0,
    height: 0,
    getContext() {
      return {
        imageSmoothingEnabled: false,
        imageSmoothingQuality: "low",
        drawImage(bitmap, x, y, width, height) {
          drawing = [bitmap.width, bitmap.height, x, y, width, height,
            this.imageSmoothingEnabled, this.imageSmoothingQuality];
        },
      };
    },
    toBlob(callback) {
      callback(new Blob([pngHeader(canvas.width, canvas.height)], { type: "image/png" }));
    },
  };
  globalThis.createImageBitmap = async () => ({
    width: 1200, height: 1800, close: () => { closed = true; },
  });
  globalThis.document = { createElement: () => canvas };
  try {
    const prepared = await prepareReferenceImage(original);
    const plan = chooseReferenceSize(1200, 1800);
    assert(prepared.resized);
    assert.notEqual(prepared.file, original);
    assert.equal(prepared.file.type, "image/png");
    assert.equal(prepared.original.width, 1200);
    assert.equal(prepared.processed.width, plan.width);
    assert.deepEqual(drawing, [1200, 1800, 0, 0, plan.width, plan.height, true, "high"]);
    assert(closed);
  } finally {
    globalThis.createImageBitmap = oldBitmap;
    globalThis.document = oldDocument;
  }
});

test("already compatible input is passed through without browser decoding", async () => {
  const file = new File([pngHeader(512, 512)], "small.png", { type: "image/png" });
  const result = await prepareReferenceImage(file);
  assert.equal(result.file, file);
  assert.equal(result.policy, "original");
  assert.equal(result.resized, false);
});
