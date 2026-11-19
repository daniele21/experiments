import assert from "node:assert/strict";
import test from "node:test";

import { enrichLiveLocalModels } from "./live-models.js";

const entries = [
  { key: "qwen-image-2.1-turbo-gguf-q4km",
    model_id: "qwen-image-2.1-turbo-gguf-q4km",
    configured: true, kind: "local", image_editing_supported: true },
  { key: "flux-3-image-klein-gguf-q5km",
    model_id: "flux-3-image-klein-gguf-q5km",
    configured: true, kind: "local", image_editing_supported: false },
  { key: "gemini-pro-image", model_id: "gemini-3-pro-image",
    configured: true, kind: "cloud" },
];

test("model selector distinguishes configured endpoint from truly resident local model", async () => {
  let calls = 0;
  const rows = await enrichLiveLocalModels(entries, "http://127.0.0.1:1235", async (url) => {
    assert.equal(url, "http://127.0.0.1:1235/v1/models");
    calls += 1;
    return new Response(JSON.stringify({ data: [
      { key: "flux-3-image-klein-gguf-q5km", image_editing_enabled: false },
    ] }), { status: 200 });
  });
  assert.equal(calls, 1);
  assert.equal(rows[0].model_resident, false);
  assert.equal(rows[0].image_editing_available, false);
  assert.equal(rows[1].model_resident, true);
  assert.equal(rows[1].image_editing_available, false);
  assert.equal(rows[1].configured, true);
  assert.equal(rows[2].model_resident, null);
  assert.match(rows[0].model_status_message, /not loaded/);
});

test("Qwen is shown as editing capable only after server explicitly reports it", async () => {
  const rows = await enrichLiveLocalModels(entries, "http://localhost:1235", async () =>
    new Response(JSON.stringify({ data: [
      { key: "qwen-image-2.1-turbo-gguf-q4km", image_editing_enabled: true },
    ] }), { status: 200 }));
  assert.equal(rows[0].model_resident, true);
  assert.equal(rows[0].image_editing_available, true);
  assert.equal(rows[1].model_resident, false);
});

test("a missing local server or unsafe base URL never falsely advertises residency", async () => {
  for (const baseUrl of ["http://public.example:1235", "", "http://127.0.0.1:1235"]) {
    const rows = await enrichLiveLocalModels(entries, baseUrl, async () => {
      throw new Error("no server");
    });
    assert.equal(rows[0].model_resident, false);
    assert.equal(rows[1].model_resident, false);
    assert.equal(rows[2].configured, true);
  }
});

test("installed local models expose one-click loading only with reachable admin API", async () => {
  const rows = await enrichLiveLocalModels(entries, "http://127.0.0.1:1235", async (url) => {
    if (url.endsWith("/v1/models")) {
      return new Response(JSON.stringify({ data: [{ key: "flux-3-image-klein-gguf-q5km" }] }), { status: 200 });
    }
    return new Response(JSON.stringify({ models: [
      { key: "flux-3-image-klein-gguf-q5km", downloaded: true },
      { key: "qwen-image-2.1-turbo-gguf-q4km", downloaded: true },
    ] }), { status: 200 });
  });
  assert.equal(rows[0].korgis_admin_enabled, true);
  assert.equal(rows[0].model_resident, false);
  assert.equal(rows[0].model_installed, true);
  assert.deepEqual(rows[0].resident_model_keys, ["flux-3-image-klein-gguf-q5km"]);
  assert.equal(rows[1].model_resident, true);
  assert.equal(rows[1].model_installed, true);
  assert.equal(rows[1].korgis_connection, "online");
});

test("status distinguishes unreachable Korgis from a cold resident model", async () => {
  const offline = await enrichLiveLocalModels(entries, "http://127.0.0.1:1235",
    async () => { throw new Error("connection refused"); });
  assert.equal(offline[1].korgis_connection, "offline");
  assert.match(offline[1].model_status_message, /unreachable/);
  const cold = await enrichLiveLocalModels(entries, "http://127.0.0.1:1235", async () =>
    new Response(JSON.stringify({ data: [] }), { status: 200 }));
  assert.equal(cold[1].korgis_connection, "online");
  assert.match(cold[1].model_status_message, /--enable-admin-api/);
});
