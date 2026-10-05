export type ModelMarker = 'circle' | 'diamond' | 'square' | 'triangle';

export interface ModelVisual {
  color: string;
  softColor: string;
  marker: ModelMarker;
}

// Three curated color families. Hashing keeps a model stable when new models are added;
// marker shape provides a second channel when many models land near similar hues.
const HUE_BANDS: Array<[number, number]> = [
  [208, 252], // blue → indigo
  [263, 314], // violet → magenta
  [145, 190], // green → teal
];

function hashString(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function modelVisual(modelSignature: string): ModelVisual {
  const hash = hashString(modelSignature);
  const band = HUE_BANDS[hash % HUE_BANDS.length];
  const step = ((hash >>> 4) % 997) / 996;
  const hue = band[0] + (band[1] - band[0]) * step;
  const saturation = 62 + ((hash >>> 14) % 16);
  const lightness = 43 + ((hash >>> 20) % 9);
  const markerIndex = (hash >>> 25) % 4;
  const markers: ModelMarker[] = ['circle', 'diamond', 'square', 'triangle'];

  return {
    color: `hsl(${hue.toFixed(1)} ${saturation}% ${lightness}%)`,
    softColor: `hsl(${hue.toFixed(1)} ${Math.max(35, saturation - 14)}% 94%)`,
    marker: markers[markerIndex],
  };
}

export function modelShortLabel(value: string): string {
  return value
    .replace(/-q\d.*$/i, '')
    .replace(/-nano-/i, ' ')
    .replace(/-v-?\d+(?:\.\d+)*-/i, ' ')
    .replace(/-luna$/i, '')
    .replaceAll('-', ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 22);
}
