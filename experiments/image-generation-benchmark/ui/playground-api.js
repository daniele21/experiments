import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { editWithKorgis, getEditingAvailability, readMultipartEdit } from "./playground-edit.js";

const UI_DIR = path.dirname(fileURLToPath(import.meta.url));
const BENCH_ROOT = path.resolve(UI_DIR, "..");
const OUTPUT_ROOT = path.resolve(
  process.env.IMAGEGEN_PLAYGROUND_ROOT || path.join(BENCH_ROOT, "playground-results"),
);
const PYTHON_SCRIPT = path.join(BENCH_ROOT, "scripts", "playground.py");
const MAX_BODY_BYTES = 16 * 1024;
const MAX_RESPONSE_BYTES = 128 * 1024;
const IMAGE_MIME = { png: "image/png", jpg: "image/jpeg", webp: "image/webp" };

export function validateGeneration(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new Error("Expected a generation request");
  }
  const keys = Object.keys(body);
  if (keys.some((key) => !["model_key", "prompt", "seed", "size", "output_format"].includes(key))) {
    throw new Error("Unexpected generation parameter");
  }
  if (typeof body.model_key !== "string" ||
      !/^[a-z0-9][a-z0-9._-]{0,99}$/.test(body.model_key)) {
    throw new Error("Choose a valid engine");
  }
  if (typeof body.prompt !== "string" ||
      body.prompt.trim().length < 1 || body.prompt.length > 4000) {
    throw new Error("Write a prompt between 1 and 4000 characters");
  }
  if (body.seed !== undefined && body.seed !== null &&
      (!Number.isSafeInteger(body.seed) || body.seed < 0 || body.seed > 2147483647)) {
    throw new Error("Seed must be an integer from 0 to 2147483647");
  }
  for (const key of ["size", "output_format"]) {
    if (body[key] !== undefined && body[key] !== null &&
        (typeof body[key] !== "string" || body[key].length > 32 ||
         !/^[a-z0-9]+(?:x[a-z0-9]+)?$/.test(body[key]))) {
      throw new Error("Invalid image size or output file format");
    }
  }
  return {
    model_key: body.model_key,
    prompt: body.prompt.trim(),
    seed: body.seed ?? null,
    size: body.size ?? null,
    output_format: body.output_format ?? null,
  };
}

function send(response, status, payload) {
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.end(JSON.stringify(payload));
}

async function readBody(request) {
  let length = 0;
  const parts = [];
  for await (const part of request) {
    length += part.length;
    if (length > MAX_BODY_BYTES) {
      const error = new Error("Request body exceeds 16 KiB");
      error.status = 413;
      throw error;
    }
    parts.push(part);
  }
  try {
    return JSON.parse(Buffer.concat(parts).toString("utf8"));
  } catch {
    throw new Error("Expected JSON request body");
  }
}

function sameOrigin(request) {
  const origin = request.headers.origin;
  if (!origin) return true; // e.g. local curl
  const expectedHost = request.headers.host;
  if (!expectedHost) return false;
  try {
    const parsed = new URL(origin);
    return (parsed.protocol === "http:" || parsed.protocol === "https:") &&
      parsed.host === expectedHost &&
      ["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname);
  } catch {
    return false;
  }
}

function runPython(action, { model_key, prompt, seed, size, output_format } = {}) {
  const args = ["run", "--frozen", "python", PYTHON_SCRIPT, action];
  if (action === "generate") {
    args.push("--model", model_key, "--output-root", OUTPUT_ROOT);
    if (seed !== null && seed !== undefined) args.push("--seed", String(seed));
    if (size) args.push("--size", size);
    if (output_format) args.push("--output-format", output_format);
  }
  return new Promise((resolve, reject) => {
    const child = spawn("uv", args, {
      cwd: BENCH_ROOT,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      shell: false,
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error);
      else resolve(value);
    };
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      finish(new Error("Generation exceeded the 20-minute playground limit"));
    }, action === "models" ? 15000 : 20 * 60 * 1000);
    child.stdout.on("data", (buf) => {
      stdout += buf.toString("utf8");
      if (stdout.length > MAX_RESPONSE_BYTES) {
        child.kill("SIGTERM");
        finish(new Error("Engine returned an oversized response"));
      }
    });
    child.stderr.on("data", (buf) => {
      stderr = (stderr + buf.toString("utf8")).slice(-4096);
    });
    child.on("error", (error) => finish(error));
    child.on("close", (code) => {
      if (settled) return;
      let parsed;
      try {
        parsed = JSON.parse(stdout.trim().split("\n").at(-1) || "{}");
      } catch {
        finish(new Error("Image engine returned an invalid response"));
        return;
      }
      if (code !== 0 || parsed.error) {
        finish(new Error(String(parsed.error || "Image engine failed").slice(0, 300)));
        return;
      }
      finish(null, parsed);
    });
    if (action === "generate") {
      child.stdin.end(JSON.stringify({ prompt }));
    } else {
      child.stdin.end();
    }
  });
}

export function playgroundApi() {
  let generating = false;
  async function middleware(request, response, next) {
    const url = new URL(request.url, "http://127.0.0.1");
    const pathname = url.pathname;
    if (!pathname.startsWith("/api/playground/")) return next();

    try {
      if (pathname === "/api/playground/models" && request.method === "GET") {
        const catalog = await runPython("models");
        const models = await Promise.all((catalog.models || []).map(async (model) => ({
          ...model,
          image_editing_available: await getEditingAvailability(
            model, process.env.KORGIS_BASE_URL,
          ),
        })));
        send(response, 200, { models });
        return;
      }
      if (pathname === "/api/playground/image" && request.method === "GET") {
        const id = url.searchParams.get("id") || "";
        if (!/^[0-9a-f]{32}$/.test(id)) {
          send(response, 400, { error: "Invalid image identifier" });
          return;
        }
        const folder = path.join(OUTPUT_ROOT, id);
        const manifest = JSON.parse(await fs.readFile(path.join(folder, "result.json"), "utf8"));
        const ext = path.extname(manifest.filename || "").slice(1);
        if (!Object.hasOwn(IMAGE_MIME, ext) || manifest.filename !== `image.${ext}`) {
          throw new Error("Invalid stored image");
        }
        const bytes = await fs.readFile(path.join(folder, manifest.filename));
        response.statusCode = 200;
        response.setHeader("Content-Type", IMAGE_MIME[ext]);
        response.setHeader("Cache-Control", "private, no-store");
        response.setHeader("X-Content-Type-Options", "nosniff");
        response.end(bytes);
        return;
      }
      if (pathname === "/api/playground/generate" && request.method === "POST") {
        if (!sameOrigin(request)) {
          send(response, 403, { error: "Cross-origin generation is not allowed" });
          return;
        }
        const body = validateGeneration(await readBody(request));
        if (generating) {
          send(response, 409, { error: "An image is already being generated" });
          return;
        }
        generating = true;
        try {
          send(response, 200, await runPython("generate", body));
        } finally {
          generating = false;
        }
        return;
      }
      if (pathname === "/api/playground/edit" && request.method === "POST") {
        if (!sameOrigin(request)) {
          send(response, 403, { error: "Cross-origin editing is not allowed" });
          return;
        }
        if (generating) {
          send(response, 409, { error: "An image operation is already running" });
          return;
        }
        generating = true;
        try {
          const input = await readMultipartEdit(request);
          const catalog = await runPython("models");
          const result = await editWithKorgis(input, {
            models: catalog.models || [],
            baseUrl: process.env.KORGIS_BASE_URL,
            outputRoot: OUTPUT_ROOT,
          });
          send(response, 200, result);
        } finally {
          generating = false;
        }
        return;
      }
      send(response, 405, { error: "Unsupported playground endpoint" });
    } catch (error) {
      const status = error?.status || (error?.code === "ENOENT" ? 404 : 400);
      send(response, status, {
        error: error instanceof Error ? error.message : "Playground request failed",
      });
    }
  }
  return {
    name: "imagegen-playground-api",
    configureServer(server) { server.middlewares.use(middleware); },
    configurePreviewServer(server) { server.middlewares.use(middleware); },
  };
}
