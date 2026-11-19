import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  DEFAULT_COMPARE_PROMPT, REVIEW_CRITERIA, defaultCompareModels,
  comparisonPlan, emptyArm, exampleBenchmarkCommand, makeComparisonReceipt,
  shuffleForBlind,
} from "./prompt-compare.js";

const models = [
  {
    key: "qwen-image-2.1-turbo-gguf-q4km",
    name: "Qwen Turbo", model_id: "qwen-image-2.1-turbo-gguf-q4km",
    kind: "local", provider: "korgis-image", configured: true,
    generation: { size: "1024x1024", output_format: "png", num_inference_steps: 8 },
    benchmark_mapping: { resolution: "1K", aspect_ratio: "1:1" },
  },
  {
    key: "gemini-pro-image",
    name: "Gemini Pro Image", model_id: "gemini-3-pro-image",
    kind: "cloud", provider: "gemini-image", configured: true,
    generation: { response_format: { type: "image", mime_type: "image/png",
      aspect_ratio: "1:1", image_size: "1K" } },
    benchmark_mapping: { resolution: "1K", aspect_ratio: "1:1" },
  },
  {
    key: "openai-sunburst",
    name: "GPT Image Sunburst", model_id: "gpt-image-2.5-sunburst",
    kind: "cloud", provider: "openai-image", configured: true,
    generation: { size: "1024x1024", output_format: "png", quality: "high" },
    benchmark_mapping: { resolution: "1K", aspect_ratio: "1:1" },
  },
];

test("quick comparison defaults to configured Qwen, Gemini and GPT Image", () => {
  assert.deepEqual(defaultCompareModels(models), models.map((m) => m.key));
  assert.deepEqual(defaultCompareModels(models.map((m) =>
    m.key === "gemini-pro-image" ? { ...m, configured: false } : m)),
  [models[0].key, models[2].key]);
  assert.match(DEFAULT_COMPARE_PROMPT, /LEFT/);
  assert.match(DEFAULT_COMPARE_PROMPT, /LOCAL AI, REAL CONTROL/);
});

test("one-prompt plan enforces configured distinct engines and literal shared prompt", () => {
  const plan = comparisonPlan(models, models.map((m) => m.key), "  Same prompt  ");
  assert.equal(plan.prompt, "Same prompt");
  assert.equal(plan.models.length, 3);
  assert.equal(plan.comparableDefaults, true);
  assert.equal(plan.includesCloud, true);
  assert.equal(plan.imageIntent, "square / approximately 1K");
  assert.throws(() => comparisonPlan(models, [models[0].key], "Prompt"), /2 and 5/);
  assert.throws(() => comparisonPlan(models, [models[0].key, models[0].key], "Prompt"), /distinct/);
  assert.throws(() => comparisonPlan(models, [models[0].key, "unknown"], "Prompt"), /not configured/);
  assert.throws(() => comparisonPlan(models, [models[0].key, models[1].key], " "), /Enter a comparison prompt/);
  assert.equal(comparisonPlan([
    models[0], { ...models[1], benchmark_mapping: { resolution: "2K", aspect_ratio: "1:1" } },
  ], [models[0].key, models[1].key], "Prompt").comparableDefaults, false);
});

test("blind shuffle is independent of the fixed provider launch order", () => {
  const keys = models.map((m) => m.key);
  const shuffled = shuffleForBlind(keys, () => 0);
  assert.deepEqual(shuffled, [keys[1], keys[2], keys[0]]);
  assert.deepEqual(keys, models.map((m) => m.key));
});

test("receipt contains model provenance, image hashes, runtime, errors and blind scores", () => {
  const plan = comparisonPlan(models, models.map((m) => m.key), "Compare");
  const arms = models.map(emptyArm);
  arms[0] = { ...arms[0], status: "success",
    result: { id: "a", image_url: "/api/playground/image?id=a",
      seed_requested: 42, seed_effective: 42, mime_type: "image/png",
      sha256: "abc123", generation: { size: "1024x1024" }, latency_ms: 202000 },
  };
  arms[1] = { ...arms[1], status: "error", error: "Provider unavailable" };
  arms[2] = { ...arms[2], status: "success",
    result: { id: "c", image_url: "/api/playground/image?id=c",
      seed_requested: null, seed_effective: null,
      mime_type: "image/png", generation: { size: "1024x1024" },
      latency_ms: 12800 },
  };
  const review = { [models[0].key]: { prompt_adherence: 5, visual_quality: 3, text_fidelity: 9 } };
  const receipt = makeComparisonReceipt(plan, arms, {
    comparisonId: "run-1",
    startedAt: "2026-11-19T08:00:00Z",
    completedAt: "2026-11-19T08:05:00Z",
    blindOrder: [models[2].key, models[0].key, models[1].key],
    reviews: review,
  });
  assert.equal(receipt.schema, "experiments.quick_image_compare.v1");
  assert.equal(receipt.arms.length, 3);
  assert.equal(receipt.arms[0].scores.prompt_adherence, 5);
  assert.equal(receipt.arms[0].scores.visual_quality, 3);
  assert.equal(receipt.arms[0].scores.text_fidelity, null);
  assert.equal(receipt.arms[0].output.sha256, "abc123");
  assert.equal(receipt.arms[1].output, null);
  assert.equal(receipt.arms[1].error, "Provider unavailable");
  assert.equal(receipt.arms[2].output.seed_requested, null);
  assert.deepEqual(receipt.blind_order, [models[2].key, models[0].key, models[1].key]);
  assert.equal(REVIEW_CRITERIA.length, 3);
});

test("benchmark command invokes the existing runner in dry-run mode only", () => {
  assert.equal(exampleBenchmarkCommand([models[0].key, models[1].key]),
    `uv run python scripts/run_benchmark.py --models ${models[0].key},${models[1].key} --profile smoke --output-dir results --dry-run`);
  assert.throws(() => exampleBenchmarkCommand(["foo; rm -rf /", "bar"]), /valid model/);
});

test("compare UI uses existing safe Playground endpoint, not provider credentials", () => {
  const source = readFileSync(fileURLToPath(new URL("./PromptCompare.jsx", import.meta.url)), "utf8");
  assert.match(source, /fetch\("\/api\/playground\/generate"/);
  assert.match(source, /for \(const model of plan\.models\)/);
  assert.match(source, /Export JSON evidence/);
  assert.match(source, /Reveal models/);
  assert.doesNotMatch(source, /OPENAI_API_KEY|GEMINI_API_KEY/);
});
