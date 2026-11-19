/** Ground local image-model readiness in the active Korgis runtime.
 * The UI can distinguish missing configuration, unreachable server, cold
 * models and admin mode without inventing local availability.
 */
import { korgisOrigin } from "./playground-edit.js";

export async function enrichLiveLocalModels(models, baseUrl, fetchImpl = fetch) {
  const origin = korgisOrigin(baseUrl);
  const hasLocal = models.some((model) => model.kind === "local");
  let loaded = [];
  let connection = origin ? "offline" : "unconfigured";
  let adminEnabled = false;
  let registry = [];
  if (origin && hasLocal) {
    try {
      const response = await fetchImpl(`${origin}/v1/models`, {
        headers: { accept: "application/json" }, signal: AbortSignal.timeout(2500),
      });
      if (response.ok) {
        const payload = await response.json();
        if (Array.isArray(payload?.data)) {
          loaded = payload.data;
          connection = "online";
        }
      }
    } catch { /* Unreachable or still starting. */ }
    if (connection === "online") {
      try {
        const response = await fetchImpl(`${origin}/api/v1/models/registry`, {
          headers: { accept: "application/json" }, signal: AbortSignal.timeout(2500),
        });
        if (response.ok) {
          const payload = await response.json();
          if (Array.isArray(payload?.models)) {
            registry = payload.models;
            adminEnabled = true;
          }
        }
      } catch { /* No admin API available: status is still truthful. */ }
    }
  }
  const installedByKey = new Map(registry.map((entry) => [entry.key, entry.downloaded]));
  const localIds = new Set(models.filter((model) => model.kind === "local")
    .map((model) => model.model_id));
  const residentKeys = loaded.filter((entry) => localIds.has(entry.key))
    .map((entry) => entry.key);
  return models.map((model) => {
    if (model.kind !== "local") return { ...model, model_resident: null };
    const live = loaded.find((item) => item?.key === model.model_id);
    const installed = live ? true : (
      installedByKey.has(model.model_id) ? installedByKey.get(model.model_id) === true : null
    );
    const modelResident = Boolean(live);
    const statusMessage = connection === "unconfigured"
      ? "Set KORGIS_BASE_URL on the Playground server."
      : connection === "offline"
        ? "Korgis is unreachable. Start the server on the configured local port."
        : modelResident ? null
          : !adminEnabled
            ? "Model not loaded in Korgis. Restart it with --enable-admin-api to load models here."
            : installed === false
              ? "Required model files are not installed locally. No automatic downloads."
              : "Model installed but not loaded. Load it from this Playground.";
    return {
      ...model,
      model_resident: modelResident,
      model_installed: installed,
      korgis_connection: connection,
      korgis_admin_enabled: adminEnabled,
      resident_model_keys: residentKeys,
      image_editing_available: Boolean(live?.image_editing_enabled &&
        model.image_editing_supported),
      model_status_message: statusMessage,
    };
  });
}
