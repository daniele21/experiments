/** Loopback-only, explicit local image-runtime lifecycle control for the Playground.
 * No model downloads, arbitrary URLs, or automatic eviction.
 */
import { korgisOrigin } from "./playground-edit.js";

export class LocalRuntimeError extends Error {
  constructor(message, status = 409, code = "runtime_error") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function keyName(value) {
  return typeof value === "string" &&
    /^[a-z0-9][a-z0-9._-]{0,99}$/.test(value);
}

export function validateLocalRuntimeAction(body, catalog) {
  if (!body || typeof body !== "object" || Array.isArray(body) ||
      Object.keys(body).some((key) => !["action", "model_key", "replace_key"].includes(key))) {
    throw new LocalRuntimeError("Invalid local model action", 400);
  }
  if (!["load", "replace"].includes(body.action) || !keyName(body.model_key)) {
    throw new LocalRuntimeError("Choose a valid local model action", 400);
  }
  const local = new Map(catalog.filter((model) => model.kind === "local")
    .map((model) => [model.key, model]));
  const target = local.get(body.model_key);
  if (!target || !keyName(target.model_id)) {
    throw new LocalRuntimeError("Only catalogued local image models may be loaded", 400);
  }
  if (body.action === "load" && body.replace_key !== undefined) {
    throw new LocalRuntimeError("Load must not select a model to evict", 400);
  }
  const replacement = body.action === "replace" ? local.get(body.replace_key) : null;
  if (body.action === "replace" &&
      (!keyName(body.replace_key) || !replacement || !keyName(replacement.model_id) ||
        replacement.model_id === target.model_id)) {
    throw new LocalRuntimeError("Choose a different resident local image model to replace", 400);
  }
  return { action: body.action, target: target.model_id, replacement: replacement?.model_id ?? null };
}

function detailMessage(value) {
  const detail = value?.detail;
  if (typeof detail === "string") return detail.slice(0, 250);
  if (detail && typeof detail.message === "string") return detail.message.slice(0, 250);
  return typeof value?.error === "string" ? value.error.slice(0, 250) : null;
}

async function requestKorgis(origin, path, init = {}, fetchImpl = fetch) {
  let response;
  try {
    response = await fetchImpl(origin + path, {
      ...init,
      signal: AbortSignal.timeout(init.method && init.method !== "GET" ? 10 * 60 * 1000 : 5000),
      headers: { accept: "application/json", ...(init.headers || {}) },
    });
  } catch {
    throw new LocalRuntimeError("Korgis is unreachable on the configured loopback endpoint", 503, "offline");
  }
  let data = {};
  try { data = await response.json(); } catch { /* preserve HTTP status */ }
  if (!response.ok) {
    throw new LocalRuntimeError(
      detailMessage(data) || `Korgis request failed (HTTP ${response.status})`,
      response.status === 404 ? 409 : response.status,
      response.status === 404 ? "admin_unavailable" : "korgis_error",
    );
  }
  return data;
}

const jsonAction = (origin, path, model, fetchImpl) => requestKorgis(origin, path, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ model, no_download: true }),
}, fetchImpl);

export async function controlLocalRuntime(body, catalog, baseUrl, fetchImpl = fetch) {
  const { action, target, replacement } = validateLocalRuntimeAction(body, catalog);
  const origin = korgisOrigin(baseUrl);
  if (!origin) {
    throw new LocalRuntimeError("Configure KORGIS_BASE_URL using a loopback URL first", 409, "unconfigured");
  }

  // Check the admin API before any mutation; downloaded=false is a hard fail.
  const registry = await requestKorgis(origin, "/api/v1/models/registry", {}, fetchImpl)
    .catch((error) => {
      if (error.code === "admin_unavailable") {
        throw new LocalRuntimeError("Restart Korgis with --enable-admin-api to load models from the Playground",
          409, "admin_disabled");
      }
      throw error;
    });
  const entries = Array.isArray(registry.models) ? registry.models : [];
  const entry = entries.find((item) => item?.key === target);
  if (!entry || entry.backend !== "stable_diffusion_cpp_image") {
    throw new LocalRuntimeError("The selected image model is not registered in Korgis", 409, "not_registered");
  }
  if (entry.downloaded !== true && entry.resident !== true) {
    throw new LocalRuntimeError("The model's files are not all installed in Korgis. Verify its model directory before loading.",
      409, "files_missing");
  }
  const residentPayload = await requestKorgis(origin, "/v1/models", {}, fetchImpl);
  const residents = Array.isArray(residentPayload.data) ? residentPayload.data : [];
  if (residents.some((item) => item?.key === target)) {
    return { ok: true, model: target, already_loaded: true };
  }

  if (action === "load") {
    // Keep any current model in memory; on budget failure the user explicitly
    // chooses whether to replace it instead of evicting silently.
    const result = await jsonAction(origin, "/api/v1/models/load", target, fetchImpl);
    return { ok: true, model: target, loaded: true, korgis: result };
  }

  // Explicit one-for-one replacement only. Never evict unrelated runtimes.
  if (residents.length !== 1 || residents[0].key !== replacement) {
    throw new LocalRuntimeError("Replacement requires exactly one resident local model. Refresh engines.",
      409, "stale_residency");
  }
  const previous = entries.find((item) => item?.key === replacement);
  if (!previous || previous.backend !== "stable_diffusion_cpp_image") {
    throw new LocalRuntimeError("Refusing to replace an unrelated runtime", 409, "unsafe_replacement");
  }

  const status = await requestKorgis(origin, "/status", {}, fetchImpl);
  if ((status?.models?.[replacement]?.active_requests ?? 0) > 0) {
    throw new LocalRuntimeError("The current model is processing a request; retry after it finishes",
      409, "busy");
  }
  await requestKorgis(origin, `/api/v1/models/${encodeURIComponent(replacement)}`, {
    method: "DELETE",
  }, fetchImpl);
  try {
    // Activate updates Korgis' default route after the old model was released.
    await jsonAction(origin, "/api/v1/models/activate", target, fetchImpl);
  } catch (error) {
    try {
      await jsonAction(origin, "/api/v1/models/activate", replacement, fetchImpl);
      throw new LocalRuntimeError(
        `Unable to load ${target}; ${replacement} was restored. ${error.message}`,
        409, "restored",
      );
    } catch (restoreError) {
      if (restoreError instanceof LocalRuntimeError && restoreError.code === "restored") {
        throw restoreError;
      }
      throw new LocalRuntimeError(
        `Unable to load ${target}, and restoring ${replacement} also failed. Refresh engines and inspect Korgis logs. ${error.message}`,
        503, "restore_failed",
      );
    }
  }
  return { ok: true, model: target, replaced: replacement };
}
