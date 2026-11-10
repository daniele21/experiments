/** Fixed-origin, long-running multipart transport to local Korgis.
 *
 * Node's fetch/Undici can close an otherwise healthy request after its
 * independent default ~300 s response-header timeout. A local Qwen edit can
 * take longer than that, so use node:http with an explicit total deadline.
 * Only an already-validated loopback origin and one checked PNG are allowed.
 */
import crypto from "node:crypto";
import http from "node:http";

const MAX_REPLY_BYTES = 32 * 1024 * 1024;
export const EDIT_DEADLINE_MS = 20 * 60 * 1000;

function encodeMultipart(form) {
  const boundary = "----korgis-edit-" + crypto.randomBytes(16).toString("hex");
  const buffers = [];
  for (const [name, value] of form.entries()) {
    if (!["image", "model", "prompt", "size", "num_inference_steps", "seed"].includes(name)) {
      throw new Error("Unexpected field in local edit request");
    }
    if (typeof value === "string") {
      // Fields are controlled by the local UI and model catalog, not arbitrary
      // remote HTTP header strings.
      buffers.push(Buffer.from(
        `--${boundary}\r\nContent-Disposition: form-data; name="${name}"\r\n\r\n${value}\r\n`,
      ));
    } else {
      if (name !== "image" || value.type !== "image/png") {
        throw new Error("Only a single PNG can be uploaded");
      }
      buffers.push(Buffer.from(
        `--${boundary}\r\nContent-Disposition: form-data; name="image"; filename="source.png"\r\nContent-Type: image/png\r\n\r\n`,
      ));
      buffers.push(value);
      buffers.push(Buffer.from("\r\n"));
    }
  }
  buffers.push(Buffer.from(`--${boundary}--\r\n`));
  return { boundary, buffers };
}

export async function submitLocalEdit(origin, form, { timeoutMs = EDIT_DEADLINE_MS } = {}) {
  if (typeof origin !== "string" || !/^http:\/\/(?:127\.0\.0\.1|localhost|\[::1\])(?::\d+)?$/.test(origin)) {
    throw new Error("Editing transport requires a loopback-only Korgis origin");
  }
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > EDIT_DEADLINE_MS) {
    throw new Error("Invalid local editing deadline");
  }
  const { boundary, buffers } = encodeMultipart(form);
  const chunks = [];
  let bytes = 0;
  for (const value of buffers) {
    const buffer = value instanceof Blob ? Buffer.from(await value.arrayBuffer()) : value;
    chunks.push(buffer);
    bytes += buffer.length;
  }
  return new Promise((resolve, reject) => {
    const request = http.request(`${origin}/v1/images/edits`, {
      method: "POST",
      headers: {
        "content-type": `multipart/form-data; boundary=${boundary}`,
        "content-length": String(bytes),
        accept: "application/json",
      },
      signal: AbortSignal.timeout(timeoutMs),
    }, (response) => {
      let size = 0;
      const received = [];
      response.on("data", (part) => {
        size += part.length;
        if (size > MAX_REPLY_BYTES) {
          const error = new Error("Korgis edit response exceeded the 32 MiB limit");
          error.code = "KORGIS_RESPONSE_TOO_LARGE";
          request.destroy(error);
          return;
        }
        received.push(part);
      });
      response.on("end", () => {
        if (size > MAX_REPLY_BYTES) return;
        const status = response.statusCode >= 200 && response.statusCode <= 599
          ? response.statusCode : 502;
        resolve(new Response(Buffer.concat(received), {
          status, headers: { "content-type": "application/json" },
        }));
      });
      response.on("error", reject);
      response.on("aborted", () => {
        const error = new Error("Korgis closed the edit response before completion");
        error.code = "ECONNRESET";
        reject(error);
      });
    });
    request.on("error", reject);
    request.end(Buffer.concat(chunks, bytes));
  });
}
