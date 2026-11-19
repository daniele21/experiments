import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_SEED, MAX_SESSION_HISTORY, appendHistory, makeHistoryEntry,
  outputChoices, resolveSeed,
} from "./playground-session.js";

test("random seeds are a fresh 31-bit integer and not a reused fixed value", () => {
  assert.equal(resolveSeed("random", "42", () => 0xffffffff), MAX_SEED);
  assert.equal(resolveSeed("random", "", () => 43), 43);
  assert.equal(resolveSeed("random", "42", () => 12345), 12345);
  assert.equal(resolveSeed("fixed", "42"), 42);
  assert.equal(resolveSeed("fixed", "0"), 0);
  for (const seed of ["", "-1", "not-a-number", "4.2", "2147483648"]) {
    assert.throws(() => resolveSeed("fixed", seed), /Seed|Enter a fixed/);
  }
  assert.throws(() => resolveSeed("random", "", () => -1), /valid random/);
});

test("choices are supplied by selected model instead of a global format list", () => {
  assert.deepEqual(outputChoices({ playground: {
    sizes: ["512x512", "768x1024"], output_formats: ["png", "webp"],
  } }), { sizes: ["512x512", "768x1024"], formats: ["png", "webp"] });
  assert.deepEqual(outputChoices({}), { sizes: [], formats: [] });
});

test("history records source/provenance and bounds the tab to twelve results", () => {
  const make = (id, mode = "generate") => makeHistoryEntry({
    id: `id-${id}`,
    image_url: `/api/playground/image?id=${id}`,
    prompt: "Change only the object color",
    model_key: "qwen-turbo",
    seed_requested: null,
    seed_effective: id,
    mime_type: "image/webp",
    generation: { size: "768x1024" },
  }, {
    mode,
    modelName: "Qwen Turbo",
    sourceName: mode === "edit" ? "original.png" : null,
    sourceUrl: mode === "edit" ? "blob:source" : null,
    originalUrl: mode === "edit" ? "blob:original" : null,
    createdAt: 1000 + id,
  });
  let history = [];
  for (let id = 1; id <= 13; id++) {
    const result = appendHistory(history, make(id, id === 13 ? "edit" : "generate"));
    history = result.entries;
  }
  assert.equal(history.length, MAX_SESSION_HISTORY);
  assert.equal(history[0].id, "id-13");
  assert.equal(history[0].sourceName, "original.png");
  assert.equal(history[0].sourceUrl, "blob:source");
  assert.equal(history[0].originalUrl, "blob:original");
  assert.equal(history[0].format, "webp");
  assert.equal(history[0].seed, 13);
  assert.equal(history[0].prompt, "Change only the object color");
  assert.equal(history[0].createdAt, 1013);
  assert.equal(history.at(-1).id, "id-2");
  const { entries, evicted } = appendHistory(history, make(14));
  assert.equal(entries.length, 12);
  assert.deepEqual(evicted.map((item) => item.id), ["id-2"]);
  assert.equal(entries[0].id, "id-14");
});

test("Playground UI keeps history and original image data only in session memory", async () => {
  const { readFileSync } = await import("node:fs");
  const { fileURLToPath } = await import("node:url");
  const file = fileURLToPath(new URL("./Playground.jsx", import.meta.url));
  const source = readFileSync(file, "utf8");
  assert.match(source, /setHistory\(/);
  assert.match(source, /URL\.revokeObjectURL/);
  assert.match(source, /Temporary list for this tab/);
  assert.match(source, /sourceName/);
  assert.match(source, /pg-t2i-format/);
  assert.match(source, /pg-t2i-size/);
  assert.match(source, /Random each time/);
  assert.doesNotMatch(source, /localStorage\.|sessionStorage\./);
});
