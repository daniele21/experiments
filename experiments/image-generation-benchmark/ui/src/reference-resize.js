/** Local-only input preparation for reference-based image editing.
 *
 * Dimension selection is deterministic and versioned. Pixel interpolation is
 * delegated to the browser's high-quality canvas implementation; its output
 * may vary slightly across browsers/OSes. No crop, padding or upscaling.
 */
export const MAX_PREPARED_PIXELS = 1024 * 1024;
export const MAX_PREPARED_SIDE = 2048;
export const MAX_ORIGINAL_PIXELS = 24 * 1024 * 1024;
export const RESIZE_GRID = 32;
export const RESIZE_POLICY = "fit-1mp-grid32-canvas-high-v1";
export const MAX_ORIGINAL_BYTES = 8 * 1024 * 1024;
const PNG_MAGIC = [137, 80, 78, 71, 13, 10, 26, 10];

export function chooseReferenceSize(width, height) {
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) ||
      width < 32 || height < 32 || width * height > MAX_ORIGINAL_PIXELS ||
      width > 16384 || height > 16384) {
    throw new Error("Source PNG dimensions are unsupported (max 24 megapixels, min 32px per side).");
  }
  if (width * height <= MAX_PREPARED_PIXELS &&
      width <= MAX_PREPARED_SIDE && height <= MAX_PREPARED_SIDE) {
    return { width, height, resized: false, policy: "original" };
  }
  const scale = Math.min(
    1,
    Math.sqrt(MAX_PREPARED_PIXELS / (width * height)),
    MAX_PREPARED_SIDE / width,
    MAX_PREPARED_SIDE / height,
  );
  // Quantize both dimensions to a 32px grid for stable diffusion processing.
  // Floor, rather than round, ensures the pixel budget is never exceeded.
  const outWidth = Math.floor(width * scale / RESIZE_GRID) * RESIZE_GRID;
  const outHeight = Math.floor(height * scale / RESIZE_GRID) * RESIZE_GRID;
  if (outWidth < 32 || outHeight < 32) {
    throw new Error("Image is too narrow to resize without distorting it.");
  }
  return {
    width: outWidth, height: outHeight, resized: true, policy: RESIZE_POLICY,
  };
}

export function matchedOutputSize(width, height) {
  // The engine output must always be grid-aligned, even if a small source
  // PNG was left unmodified for input.
  const w = Math.max(32, Math.floor(width / RESIZE_GRID) * RESIZE_GRID);
  const h = Math.max(32, Math.floor(height / RESIZE_GRID) * RESIZE_GRID);
  if (w * h > MAX_PREPARED_PIXELS || w > MAX_PREPARED_SIDE || h > MAX_PREPARED_SIDE) {
    throw new Error("Cannot match output to this image shape.");
  }
  return `${w}x${h}`;
}

export async function readReferenceHeader(file) {
  if (!file || file.type !== "image/png" ||
      !file.name?.toLowerCase().endsWith(".png")) {
    throw new Error("Choose a PNG image. JPEG and WebP are not supported yet.");
  }
  if (file.size > MAX_ORIGINAL_BYTES) {
    throw new Error("Source PNG exceeds 8 MiB. Export a smaller PNG first.");
  }
  const bytes = new Uint8Array(await file.slice(0, 33).arrayBuffer());
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (bytes.length !== 33 ||
      PNG_MAGIC.some((value, index) => bytes[index] !== value) ||
      view.getUint32(8) !== 13 ||
      String.fromCharCode(...bytes.slice(12, 16)) !== "IHDR") {
    throw new Error("This file is not a valid PNG.");
  }
  const width = view.getUint32(16);
  const height = view.getUint32(20);
  // Checks the raw PNG dimensions before any expensive bitmap decode.
  chooseReferenceSize(width, height);
  return { width, height };
}

export async function prepareReferenceImage(file) {
  const original = await readReferenceHeader(file);
  const plan = chooseReferenceSize(original.width, original.height);
  if (!plan.resized) {
    return { file, original, processed: original, resized: false, policy: "original" };
  }
  let bitmap;
  try {
    bitmap = await createImageBitmap(file);
    if (bitmap.width !== original.width || bitmap.height !== original.height) {
      throw new Error("The PNG decoder disagrees with its declared dimensions.");
    }
    const canvas = document.createElement("canvas");
    canvas.width = plan.width;
    canvas.height = plan.height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas resizing is unavailable in this browser.");
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.drawImage(bitmap, 0, 0, plan.width, plan.height);
    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob((result) => {
        if (result) resolve(result);
        else reject(new Error("Could not encode the resized PNG."));
      }, "image/png");
    });
    if (blob.size > MAX_ORIGINAL_BYTES) {
      throw new Error("Resized PNG still exceeds 8 MiB. Export a smaller source image.");
    }
    const basename = file.name.replace(/\.png$/i, "") || "reference";
    const prepared = new File([blob], `${basename}-prepared.png`, { type: "image/png" });
    return {
      file: prepared,
      original,
      processed: { width: plan.width, height: plan.height },
      resized: true,
      policy: plan.policy,
    };
  } finally {
    bitmap?.close();
  }
}
