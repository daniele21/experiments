/** Local-only Image-to-Image proxy and bounded result persistence.
 *
 * Browser uploads never reach a cloud service. Korgis is the only inference
 * owner; this file is merely a development UI transport.
 */
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";

export const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
export const MAX_EDIT_BODY_BYTES = MAX_IMAGE_BYTES + 64 * 1024;
const MAX_KORGIS_RESPONSE_BYTES = 32 * 1024 * 1024;
const PNG_HEADER = Buffer.from("89504e470d0a1a0a", "hex");
const SAFE_FIELDS = new Set(["image", "model_key", "prompt", "size", "seed", "num_inference_steps"]);
const EDIT_SIZES = new Set(["512x512", "768x768", "1024x1024", "1024x768", "768x1024"]);

export function korgisOrigin(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" ||
        !["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname) ||
        parsed.username || parsed.password || parsed.search || parsed.hash ||
        !["/", ""].includes(parsed.pathname)) return null;
    return parsed.origin;
  } catch {
    return null;
  }
}

function clientError(message, status = 400) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function crc32(data) {
  let crc = 0xFFFFFFFF;
  for (const byte of data) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ ((crc & 1) ? 0xEDB88320 : 0);
    }
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

export function inspectPng(bytes) {
  if (!Buffer.isBuffer(bytes) || bytes.length < 45 ||
      bytes.length > MAX_IMAGE_BYTES ||
      !bytes.subarray(0, 8).equals(PNG_HEADER) ||
      bytes.toString("ascii", 12, 16) !== "IHDR" ||
      bytes.readUInt32BE(8) !== 13 ||
      crc32(bytes.subarray(12, 29)) !== bytes.readUInt32BE(29)) {
    throw clientError("A valid PNG under 8 MiB is required");
  }
  const width = bytes.readUInt32BE(16);
  const height = bytes.readUInt32BE(20);
  if (width < 32 || height < 32 || width > 2048 || height > 2048 ||
      width * height > 1024 * 1024) {
    throw clientError("Input PNG must be at most 1 megapixel (32–2048 px per side)");
  }
  // A valid PNG must contain at least one IDAT plus a terminal IEND.
  let cursor = 8;
  let sawIdat = false;
  let ended = false;
  while (cursor + 12 <= bytes.length) {
    const length = bytes.readUInt32BE(cursor);
    if (length > bytes.length - cursor - 12) break;
    const tag = bytes.toString("ascii", cursor + 4, cursor + 8);
    const after = cursor + 12 + length;
    if (crc32(bytes.subarray(cursor + 4, after - 4)) !== bytes.readUInt32BE(after - 4)) break;
    if (tag === "IDAT") sawIdat = true;
    if (tag === "IEND" && length === 0 && after === bytes.length) {
      ended = true;
      break;
    }
    cursor = after;
  }
  if (!sawIdat || !ended) throw clientError("Invalid or incomplete PNG image");
  return { width, height };
}

export async function readMultipartEdit(request) {
  const type = request.headers["content-type"] || "";
  if (!/^multipart\/form-data\s*;.*boundary=/i.test(type)) {
    throw clientError("Expected multipart/form-data with one PNG upload", 415);
  }
  const declared = Number(request.headers["content-length"] || 0);
  if (Number.isFinite(declared) && declared > MAX_EDIT_BODY_BYTES) {
    throw clientError("Image upload exceeds the 8 MiB limit", 413);
  }
  let length = 0;
  const parts = [];
  for await (const chunk of request) {
    length += chunk.length;
    if (length > MAX_EDIT_BODY_BYTES) {
      throw clientError("Image upload exceeds the 8 MiB limit", 413);
    }
    parts.push(chunk);
  }
  let form;
  try {
    form = await new Request("http://localhost/edit", {
      method: "POST", headers: { "content-type": type },
      body: Buffer.concat(parts),
    }).formData();
  } catch {
    throw clientError("Invalid multipart image upload");
  }
  const entries = [...form.entries()];
  if (entries.length > SAFE_FIELDS.size || entries.some(([key]) => !SAFE_FIELDS.has(key))) {
    throw clientError("Unexpected or repeated image editing fields");
  }
  if (new Set(entries.map(([key]) => key)).size !== entries.length) {
    throw clientError("Repeated image editing fields are not allowed");
  }
  const file = form.get("image");
  if (!file || typeof file.arrayBuffer !== "function" || file.type !== "image/png") {
    throw clientError("Choose one PNG file", 415);
  }
  if (file.size > MAX_IMAGE_BYTES) throw clientError("Image exceeds 8 MiB", 413);
  const bytes = Buffer.from(await file.arrayBuffer());
  const dimensions = inspectPng(bytes);
  const modelKey = form.get("model_key");
  if (typeof modelKey !== "string" ||
      !/^[a-z0-9][a-z0-9._-]{0,99}$/.test(modelKey)) {
    throw clientError("Choose a valid model");
  }
  const prompt = form.get("prompt");
  if (typeof prompt !== "string" || !prompt.trim() || prompt.length > 4000) {
    throw clientError("Prompt must contain 1–4000 characters");
  }
  const size = form.get("size") || "512x512";
  if (typeof size !== "string" || !EDIT_SIZES.has(size)) {
    throw clientError("Choose a supported editing resolution");
  }
  const seedText = form.get("seed");
  const seed = seedText === null || seedText === "" ? null : Number(seedText);
  if (seed !== null && (!Number.isSafeInteger(seed) || seed < 0 || seed > 2147483647)) {
    throw clientError("Seed must be an integer from 0 to 2147483647");
  }
  const stepsText = form.get("num_inference_steps");
  const steps = stepsText === null || stepsText === "" ? 8 : Number(stepsText);
  if (!Number.isSafeInteger(steps) || steps !== 8) {
    throw clientError("Qwen Turbo editing currently requires 8 inference steps");
  }
  return { model_key: modelKey, prompt: prompt.trim(), size, seed, steps, bytes, dimensions };
}

async function readLimited(response) {
  let length = 0;
  const parts = [];
  if (!response.body) throw clientError("Korgis returned an empty response", 502);
  for await (const chunk of response.body) {
    length += chunk.length;
    if (length > MAX_KORGIS_RESPONSE_BYTES) {
      await response.body.cancel?.().catch(() => {});
      throw clientError("Korgis returned an oversized image", 502);
    }
    parts.push(Buffer.from(chunk));
  }
  try {
    return JSON.parse(Buffer.concat(parts).toString("utf8"));
  } catch {
    throw clientError("Korgis returned invalid JSON", 502);
  }
}

function errorMessage(payload, code) {
  const detail = payload?.detail;
  const message = (typeof detail === "object" ? detail?.message : detail)
    || payload?.error?.message || payload?.error;
  if (code === 400 && (detail?.code === "unsupported_task" ||
      /image editing|image edits|not enabled/i.test(String(message)))) {
    return "Image editing is not enabled in Korgis. Restart with --image-editing-enabled.";
  }
  if (code === 503 || detail?.code === "resource_exhausted") {
    return "Korgis declined the edit due to memory pressure or unavailable resources. Free RAM and retry.";
  }
  return typeof message === "string" ? message.slice(0, 280)
    : `Korgis image editing failed (HTTP ${code})`;
}

export async function getEditingAvailability(model, baseUrl, fetchImpl = fetch) {
  if (!model?.image_editing_supported || model.kind !== "local") return false;
  const origin = korgisOrigin(baseUrl);
  if (!origin) return false;
  try {
    const response = await fetchImpl(`${origin}/v1/models`, {
      signal: AbortSignal.timeout(2500), headers: { Accept: "application/json" },
    });
    if (!response.ok) return false;
    const payload = await response.json();
    return Array.isArray(payload?.data) && payload.data.some((item) =>
      item.key === model.model_id && item.image_editing_enabled === true);
  } catch {
    return false;
  }
}

export async function editWithKorgis(input, {
  models, baseUrl, outputRoot, fetchImpl = fetch,
}) {
  const model = models.find((row) => row.key === input.model_key);
  if (!model || !model.image_editing_supported || model.kind !== "local") {
    throw clientError("This engine does not support local image editing");
  }
  const origin = korgisOrigin(baseUrl);
  if (!origin) throw clientError("Set KORGIS_BASE_URL to a loopback Korgis server", 503);
  if (!(await getEditingAvailability(model, origin, fetchImpl))) {
    throw clientError("Start Korgis with --image-editing-enabled and refresh the engine list", 409);
  }

  const form = new FormData();
  form.set("image", new Blob([input.bytes], { type: "image/png" }), "source.png");
  form.set("model", model.model_id);
  form.set("prompt", input.prompt);
  form.set("size", input.size);
  form.set("num_inference_steps", String(input.steps));
  if (input.seed !== null) form.set("seed", String(input.seed));

  let upstream;
  try {
    upstream = await fetchImpl(`${origin}/v1/images/edits`, {
      method: "POST", body: form, signal: AbortSignal.timeout(20 * 60 * 1000),
    });
  } catch (error) {
    throw clientError(error?.name === "TimeoutError"
      ? "Korgis editing exceeded the 20-minute limit"
      : "Cannot connect to Korgis image editing API", 502);
  }
  const payload = await readLimited(upstream);
  if (!upstream.ok) throw clientError(
    errorMessage(payload, upstream.status),
    [400, 413, 415, 409, 503].includes(upstream.status) ? upstream.status : 502,
  );
  const encoded = payload?.data?.[0]?.b64_json;
  if (typeof encoded !== "string" || !/^[a-zA-Z0-9+/]+={0,2}$/.test(encoded) ||
      encoded.length > MAX_KORGIS_RESPONSE_BYTES) {
    throw clientError("Korgis returned no valid image bytes", 502);
  }
  const image = Buffer.from(encoded, "base64");
  if (!image.length || image.toString("base64") !== encoded) {
    throw clientError("Korgis returned invalid image encoding", 502);
  }
  const output = inspectPng(image);
  const id = crypto.randomUUID().replaceAll("-", "");
  const folder = path.join(outputRoot, id);
  await fs.mkdir(outputRoot, { recursive: true });
  await fs.mkdir(folder);
  try {
    const meta = payload?.korgis || {};
    const manifest = {
      id, mode: "edit", model_key: model.key, model_id: model.model_id,
      provider: "korgis-image", runtime: model.runtime, kind: "local",
      prompt: input.prompt, seed_requested: input.seed,
      seed_effective: Number.isInteger(meta.seed) ? meta.seed : null,
      generation: { size: input.size, num_inference_steps: input.steps },
      mime_type: "image/png", filename: "image.png",
      size_bytes: image.length,
      sha256: crypto.createHash("sha256").update(image).digest("hex"),
      source_sha256: crypto.createHash("sha256").update(input.bytes).digest("hex"),
      source_width: input.dimensions.width, source_height: input.dimensions.height,
      width: output.width, height: output.height,
      latency_ms: Number.isFinite(meta.latency_ms) ? meta.latency_ms : null,
    };
    await fs.writeFile(path.join(folder, "image.png"), image);
    await fs.writeFile(path.join(folder, "result.json"), JSON.stringify(manifest, null, 2));
    return { ...manifest, image_url: `/api/playground/image?id=${id}` };
  } catch (error) {
    await fs.rm(folder, { recursive: true, force: true });
    throw error;
  }
}
