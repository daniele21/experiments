import assert from "node:assert/strict";
import test from "node:test";
import { controlLocalRuntime, validateLocalRuntimeAction } from "./local-runtime-control.js";

const local = [
  { key: "flux", model_id: "flux", kind: "local" },
  { key: "qwen", model_id: "qwen", kind: "local" },
  { key: "cloud", model_id: "cloud", kind: "cloud" },
];
const origin = "http://127.0.0.1:1235";
const json = (body, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
function fakeFetch(behavior = {}) {
  const calls = [];
  const fetcher = async (url, init = {}) => {
    const method = init.method || "GET";
    const path = new URL(url).pathname;
    calls.push({ path, method, body: init.body ? JSON.parse(init.body) : null });
    if (behavior[`${method} ${path}`]) return behavior[`${method} ${path}`](init);
    if (path.endsWith("/registry")) return json({ models: [
      { key: "flux", backend: "stable_diffusion_cpp_image", downloaded: true },
      { key: "qwen", backend: "stable_diffusion_cpp_image", downloaded: true },
    ] });
    if (path.endsWith("/v1/models")) return json({ data: [{ key: "flux" }] });
    if (path.endsWith("/status")) return json({ models: { flux: { active_requests: 0 } } });
    return json({ ok: true });
  };
  return { fetcher, calls };
}

test("allowlists local model keys and rejects arbitrary admin actions", () => {
  assert.deepEqual(validateLocalRuntimeAction({ action: "load", model_key: "qwen" }, local),
    { action: "load", target: "qwen", replacement: null });
  for (const input of [
    { action: "delete", model_key: "qwen" },
    { action: "load", model_key: "cloud" },
    { action: "load", model_key: "qwen", replace_key: "flux" },
    { action: "replace", model_key: "qwen", replace_key: "cloud" },
    { action: "replace", model_key: "qwen", replace_key: "qwen" },
    { action: "replace", model_key: "../../etc/passwd", replace_key: "flux" },
  ]) assert.throws(() => validateLocalRuntimeAction(input, local));
});

test("load keeps resident model and forbids implicit weight downloads", async () => {
  const { fetcher, calls } = fakeFetch();
  const result = await controlLocalRuntime({ action: "load", model_key: "qwen" }, local, origin, fetcher);
  assert.equal(result.loaded, true);
  assert.deepEqual(calls.filter((x) => x.method !== "GET"), [{
    path: "/api/v1/models/load", method: "POST", body: { model: "qwen", no_download: true },
  }]);
});

test("replacement unloads only explicitly selected sole resident, then activates target", async () => {
  const { fetcher, calls } = fakeFetch();
  const result = await controlLocalRuntime({
    action: "replace", model_key: "qwen", replace_key: "flux",
  }, local, origin, fetcher);
  assert.equal(result.replaced, "flux");
  assert.deepEqual(calls.filter((x) => x.method !== "GET"), [
    { path: "/api/v1/models/flux", method: "DELETE", body: null },
    { path: "/api/v1/models/activate", method: "POST", body: { model: "qwen", no_download: true } },
  ]);
});

test("failed replacement attempts to restore the original model", async () => {
  const { fetcher, calls } = fakeFetch({
    "POST /api/v1/models/activate": (init) =>
      json({ detail: "Out of memory" }, JSON.parse(init.body).model === "qwen" ? 500 : 200),
  });
  await assert.rejects(
    controlLocalRuntime({ action: "replace", model_key: "qwen", replace_key: "flux" }, local, origin, fetcher),
    /was restored/,
  );
  assert.deepEqual(calls.filter((x) => x.path === "/api/v1/models/activate").map((x) => x.body.model),
    ["qwen", "flux"]);
});

test("never evicts model with missing target files or an active request", async () => {
  const missing = fakeFetch({
    "GET /api/v1/models/registry": () => json({ models: [
      { key: "qwen", backend: "stable_diffusion_cpp_image", downloaded: false },
    ] }),
  });
  await assert.rejects(controlLocalRuntime({
    action: "replace", model_key: "qwen", replace_key: "flux",
  }, local, origin, missing.fetcher), /not all installed/);
  assert.equal(missing.calls.some((x) => x.method === "DELETE"), false);

  const busy = fakeFetch({
    "GET /status": () => json({ models: { flux: { active_requests: 1 } } }),
  });
  await assert.rejects(controlLocalRuntime({
    action: "replace", model_key: "qwen", replace_key: "flux",
  }, local, origin, busy.fetcher), /processing a request/);
  assert.equal(busy.calls.some((x) => x.method === "DELETE"), false);
});

test("unreachable/invalid loopback origin and absent admin API fail closed", async () => {
  await assert.rejects(controlLocalRuntime({ action: "load", model_key: "qwen" },
    local, "http://example.com:1235", async () => json({})), /loopback/);
  const { fetcher, calls } = fakeFetch({
    "GET /api/v1/models/registry": () => json({}, 404),
  });
  await assert.rejects(controlLocalRuntime({
    action: "load", model_key: "qwen",
  }, local, origin, fetcher), /--enable-admin-api/);
  assert.equal(calls.some((x) => x.method === "POST"), false);
});
