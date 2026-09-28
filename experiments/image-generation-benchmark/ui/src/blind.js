export async function sha256Hex(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export async function buildBlindPair({ promptId, firstModel, secondModel, seed }) {
  if (firstModel === secondModel) {
    throw new Error("blind comparison requires two different models");
  }
  const digest = await sha256Hex(
    `${seed}:${promptId}:${firstModel}:${secondModel}`,
  );
  const swap = Number.parseInt(digest.at(-1), 16) % 2 === 1;
  return {
    pairId: `pair-${digest.slice(0, 16)}`,
    promptId,
    modelForA: swap ? secondModel : firstModel,
    modelForB: swap ? firstModel : secondModel,
  };
}
