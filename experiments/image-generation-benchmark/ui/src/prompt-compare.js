/** Quick visual comparisons built from the existing Playground provider API.
 * No alternate generator, no model API keys in the browser.
 */
export const DEFAULT_COMPARE_PROMPT =
  'A photorealistic premium magazine advertisement on a warm ivory background. ' +
  'In the center stands exactly one matte emerald-green ceramic mug. ' +
  'To its LEFT is one small red apple, and to its RIGHT is one closed blue notebook. ' +
  'A small clean sign in the background reads exactly "LOCAL AI, REAL CONTROL" ' +
  'in crisp, legible uppercase letters. Soft natural morning light from the left, ' +
  'realistic shadows, no extra objects, no other text. Square composition.';

export const REVIEW_CRITERIA = [
  { id: "prompt_adherence", label: "Prompt adherence" },
  { id: "visual_quality", label: "Visual quality" },
  { id: "text_fidelity", label: "Text fidelity" },
];

export const MAX_COMPARE_ARMS = 5;

const DEFAULT_ARMS = [
  "qwen-image-2.1-turbo-gguf-q4km",
  "flux-3-image-klein-gguf-q5km",
  "gemini-pro-image",
  "openai-sunburst",
];

export function isModelReady(model) {
  return Boolean(model?.configured &&
    (model.kind !== "local" || model.model_resident !== false));
}

export function defaultCompareModels(models) {
  const candidates = DEFAULT_ARMS.filter((key) =>
    models.some((model) => model.key === key && isModelReady(model)));
  if (candidates.length >= 2) return candidates;
  return models.filter(isModelReady)
    .slice(0, 3).map((model) => model.key);
}

export function comparisonPlan(models, selectedKeys, prompt) {
  if (typeof prompt !== "string" || !prompt.trim() || prompt.length > 4000) {
    throw new Error("Enter a comparison prompt between 1 and 4000 characters");
  }
  if (!Array.isArray(selectedKeys) || selectedKeys.length < 2 ||
      selectedKeys.length > MAX_COMPARE_ARMS ||
      new Set(selectedKeys).size !== selectedKeys.length) {
    throw new Error("Select between 2 and 5 distinct models");
  }
  const ordered = selectedKeys.map((key) => {
    const model = models.find((item) => item.key === key);
    if (!isModelReady(model)) {
      throw new Error(`${model?.name || key} is not ready. Load this model in Korgis, or set the cloud API key, then refresh engines.`);
    }
    return model;
  });
  // Avoid promising identical sampling settings across different providers.
  // Defaults are recorded; a "1K square" setting is a target, not proof
  // of identical generated pixel dimensions.
  return {
    prompt: prompt.trim(),
    models: ordered,
    imageIntent: "square / approximately 1K",
    comparableDefaults: ordered.every((model) =>
      model.benchmark_mapping?.aspect_ratio === "1:1" &&
      model.benchmark_mapping?.resolution === "1K"),
    includesCloud: ordered.some((model) => model.kind === "cloud"),
  };
}

export function emptyArm(model) {
  return {
    key: model.key,
    name: model.name,
    model_id: model.model_id,
    kind: model.kind,
    provider: model.provider,
    configured_generation: model.generation,
    benchmark_mapping: model.benchmark_mapping,
    status: "waiting",
    result: null,
    error: null,
  };
}

export function makeComparisonReceipt(plan, arms, {
  comparisonId, startedAt, completedAt, reviews = {}, blindOrder = [],
} = {}) {
  if (!comparisonId || !Array.isArray(arms)) throw new Error("Missing comparison evidence");
  return {
    schema: "experiments.quick_image_compare.v1",
    comparison_id: comparisonId,
    prompt: plan.prompt,
    image_intent: plan.imageIntent,
    comparable_defaults: plan.comparableDefaults,
    started_at: startedAt,
    completed_at: completedAt,
    score_scale: "1–5 manual; null means not rated",
    note: "One-prompt exploratory comparison, not a quality leaderboard. Cloud seeds are not controlled.",
    blind_order: [...blindOrder],
    arms: arms.map((arm) => ({
      model_key: arm.key,
      model_id: arm.model_id,
      provider: arm.provider,
      kind: arm.kind,
      configured_generation: arm.configured_generation,
      benchmark_mapping: arm.benchmark_mapping,
      status: arm.status,
      error: arm.error,
      output: arm.result ? {
        id: arm.result.id,
        image_url: arm.result.image_url,
        sha256: arm.result.sha256 || null,
        mime_type: arm.result.mime_type || null,
        size: arm.result.generation?.size ?? null,
        seed_requested: arm.result.seed_requested ?? null,
        seed_effective: arm.result.seed_effective ?? null,
        latency_ms: arm.result.latency_ms ?? null,
      } : null,
      scores: Object.fromEntries(
        REVIEW_CRITERIA.map(({ id }) => [
          id,
          Number.isInteger(reviews[arm.key]?.[id]) &&
          reviews[arm.key][id] >= 1 && reviews[arm.key][id] <= 5
            ? reviews[arm.key][id] : null,
        ]),
      ),
    })),
  };
}

export function shuffleForBlind(keys, random = Math.random) {
  const shuffled = [...keys];
  for (let i = shuffled.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

export function exampleBenchmarkCommand(keys) {
  if (!Array.isArray(keys) || keys.length < 2 ||
      keys.some((key) => !/^[a-z0-9][a-z0-9._-]{0,99}$/.test(key))) {
    throw new Error("Select two or more valid model keys");
  }
  return `uv run python scripts/run_benchmark.py --models ${keys.join(",")} --profile smoke --output-dir results --dry-run`;
}
