/** Ground local image-model readiness in Korgis' resident-model API.
 * KORGIS_BASE_URL is accepted only on loopback and no provider keys leak.
 */
import { korgisOrigin } from "./playground-edit.js";

export async function enrichLiveLocalModels(models, baseUrl, fetchImpl = fetch) {
  const origin = korgisOrigin(baseUrl);
  let loaded = [];
  if (origin && models.some((model) => model.kind === "local")) {
    try {
      const response = await fetchImpl(`${origin}/v1/models`, {
        headers: { accept: "application/json" }, signal: AbortSignal.timeout(2500),
      });
      if (response.ok) {
        const payload = await response.json();
        if (Array.isArray(payload?.data)) loaded = payload.data;
      }
    } catch { /* server absent/still starting: all local runtimes unavailable */ }
  }
  return models.map((model) => {
    if (model.kind !== "local") return { ...model, model_resident: null };
    const live = loaded.find((item) => item?.key === model.model_id);
    return {
      ...model,
      model_resident: Boolean(live),
      image_editing_available: Boolean(live?.image_editing_enabled &&
        model.image_editing_supported),
      model_status_message: live
        ? null
        : `Model not loaded in Korgis: ${model.model_id}. Start it and refresh engines.`,
    };
  });
}
