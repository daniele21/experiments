import test from "node:test";
import assert from "node:assert/strict";

import { validateGeneration } from "./playground-api.js";

test("a local model, prompt and seed form a safe generation request", () => {
  assert.deepEqual(
    validateGeneration({
      model_key: "qwen-image-2.1-turbo-gguf-q4km",
      prompt: "  A morning cafe  ",
      seed: 42,
    }),
    { model_key: "qwen-image-2.1-turbo-gguf-q4km", prompt: "A morning cafe", seed: 42, size: null, output_format: null },
  );
});

test("arbitrary server paths and unknown options are rejected", () => {
  assert.throws(
    () => validateGeneration({ model_key: "../../etc/passwd", prompt: "foo" }),
    /valid engine/,
  );
  assert.throws(
    () => validateGeneration({ model_key: "foo", prompt: "bar", binary_path: "/usr/bin/sh" }),
    /Unexpected generation/,
  );
});

test("reject invalid seeds and empty prompts before provider execution", () => {
  for (const seed of [-1, 1.5, "42", 2147483648, true]) {
    assert.throws(
      () => validateGeneration({ model_key: "qwen-image-2.1-turbo-gguf-q4km", prompt: "Foo", seed }),
      /Seed/,
    );
  }
  assert.throws(
    () => validateGeneration({ model_key: "qwen-image-2.1-turbo-gguf-q4km", prompt: "  " }),
    /prompt/,
  );
});

test("explicit image size and file format are validated in the proxy", () => {
  const value = validateGeneration({
    model_key: "qwen-image-2.1-turbo-gguf-q4km",
    prompt: "Generate a portrait",
    seed: 912,
    size: "768x1024",
    output_format: "webp",
  });
  assert.equal(value.size, "768x1024");
  assert.equal(value.output_format, "webp");
  for (const extras of [
    { size: "../../etc/passwd" },
    { size: 768 },
    { output_format: "image/png" },
    { output_format: "svg<script>" },
    { output_format: 123 },
  ]) {
    assert.throws(() => validateGeneration({
      model_key: "qwen-image-2.1-turbo-gguf-q4km",
      prompt: "Test", ...extras,
    }), /Invalid image size or output file format/);
  }
});
