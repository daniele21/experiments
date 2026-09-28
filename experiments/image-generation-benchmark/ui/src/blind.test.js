import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import test from "node:test";

globalThis.crypto ??= webcrypto;

const { buildBlindPair } = await import("./blind.js");

test("blind pair matches the Python benchmark contract", async () => {
  assert.deepEqual(
    await buildBlindPair({
      seed: 42,
      promptId: "text-001",
      firstModel: "gemini-pro-image",
      secondModel: "qwen-image-2.1-local",
    }),
    {
      pairId: "pair-dea3e1bf912b16e7",
      promptId: "text-001",
      modelForA: "qwen-image-2.1-local",
      modelForB: "gemini-pro-image",
    },
  );
});
