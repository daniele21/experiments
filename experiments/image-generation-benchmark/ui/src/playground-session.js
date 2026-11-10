/** Session-only Playground state; no localStorage or remote data transfer. */
export const MAX_SESSION_HISTORY = 12;
export const MAX_SEED = 2147483647;

export function resolveSeed(mode, fixedValue, random32) {
  if (mode === "random") {
    const value = random32 ? random32() : (() => {
      if (!globalThis.crypto?.getRandomValues) {
        throw new Error("Secure random seeds are unavailable in this browser");
      }
      const numbers = new Uint32Array(1);
      globalThis.crypto.getRandomValues(numbers);
      return numbers[0];
    })();
    if (!Number.isSafeInteger(value) || value < 0 || value > 0xffffffff) {
      throw new Error("Unable to choose a valid random seed");
    }
    return value & MAX_SEED;
  }
  if (mode !== "fixed" || String(fixedValue).trim() === "") {
    throw new Error("Enter a fixed seed or select Random");
  }
  const parsed = Number(fixedValue);
  if (!Number.isSafeInteger(parsed) || parsed < 0 || parsed > MAX_SEED) {
    throw new Error("Seed must be an integer from 0 to 2147483647");
  }
  return parsed;
}

export function outputChoices(model) {
  const configured = model?.playground || {};
  const sizes = Array.isArray(configured.sizes) ? configured.sizes : [];
  const formats = Array.isArray(configured.output_formats) ? configured.output_formats : [];
  return { sizes, formats };
}

export function makeHistoryEntry(result, {
  mode, modelName, sourceUrl = null, originalUrl = null,
  sourceName = null, createdAt = Date.now(),
} = {}) {
  if (!result?.id || !result?.image_url) throw new Error("A completed image is required");
  return {
    id: result.id,
    result,
    mode: mode === "edit" ? "edit" : "generate",
    modelName: modelName || result.model_key,
    createdAt,
    prompt: result.prompt || "",
    seed: result.seed_effective ?? result.seed_requested ?? null,
    format: String(result.mime_type || "image/png").replace("image/", ""),
    size: result.generation?.size || null,
    sourceUrl,
    originalUrl,
    sourceName,
  };
}

export function appendHistory(previous, entry, limit = MAX_SESSION_HISTORY) {
  if (!Number.isInteger(limit) || limit < 1) throw new Error("Invalid history limit");
  const unique = previous.filter((item) => item.id !== entry.id);
  const combined = [entry, ...unique];
  return { entries: combined.slice(0, limit), evicted: combined.slice(limit) };
}
