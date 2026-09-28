/**
 * theme.ts
 * Design tokens, color palettes, and formatting utilities for the dashboard.
 */

export const THEME = {
  colors: {
    bg: '#f8fafc',
    surface: '#ffffff',
    surfaceSubtle: '#f1f5f9',
    surfaceHover: '#f8fafc',
    border: '#e2e8f0',
    borderLight: '#f1f5f9',
    borderDark: '#cbd5e1',
    text: '#0f172a',
    textMuted: '#64748b',
    textLight: '#94a3b8',
    primary: '#0f172a',
    accent: '#4f46e5',
    accentLight: '#e0e7ff',
    success: '#059669',
    successLight: '#ecfdf5',
    warning: '#d97706',
    warningLight: '#fffbeb',
    danger: '#dc2626',
    dangerLight: '#fef2f2',
    gold: '#f59e0b',
    silver: '#94a3b8',
    bronze: '#b45309',
  },
  palette: [
    '#4f46e5', // Indigo
    '#059669', // Emerald
    '#d97706', // Amber
    '#7c3aed', // Violet
    '#0284c7', // Sky
    '#e11d48', // Rose
    '#0d9488', // Teal
    '#ea580c', // Orange
    '#475569', // Slate
  ],
  chart: {
    /**
     * Configuration for bar hover highlighting across benchmark charts.
     * Easily customizable:
     * - Amber/Gold preset: start '#f59e0b', end '#fbbf24', stroke '#d97706', glow 'rgba(245, 158, 11, 0.55)'
     * - Cyan preset: start '#06b6d4', end '#38bdf8', stroke '#0891b2', glow 'rgba(6, 182, 212, 0.55)'
     */
    barHover: {
      gradientId: 'chart-bar-hover-grad',
      startColor: '#f59e0b', // Vibrant Gold / Amber
      endColor: '#fbbf24',
      stroke: '#d97706',
      strokeWidth: 1.5,
      glow: 'rgba(245, 158, 11, 0.55)',
      dropShadow: 'drop-shadow(0 0 10px rgba(245, 158, 11, 0.65)) drop-shadow(0 2px 4px rgba(0, 0, 0, 0.15))',
      dimmedOpacity: 0.45,
    },
  },
};

/**
 * Configuration for chart bar gradients.
 * Eliminates random rainbow colors across bars in favor of a cohesive,
 * elegant 2-color or 3-color gradient.
 */
export const BAR_GRADIENT_CONFIG = {
  /** Gradient mode: 'three-color' (default) or 'two-color' */
  mode: 'three-color' as 'three-color' | 'two-color',

  /**
   * Gradient direction across charts:
   * 'vertical' - Flows vertically across all bars from top bar (best) to bottom bar (no horizontal rainbow inside a single bar).
   * 'horizontal' - Flows horizontally across each bar.
   */
  direction: 'vertical' as 'vertical' | 'horizontal',

  /** Three-color gradient: Start (0% / Top), Middle (50% / Mid), End (100% / Bottom) */
  threeColor: {
    start: '#4f46e5',  // Deep Indigo (Rank 1 / Top)
    middle: '#7c3aed', // Electric Violet (Mid ranks)
    end: '#06b6d4',    // Luminous Cyan (Bottom rank)
  },

  /** Two-color gradient: Start (0% / Top), End (100% / Bottom) */
  twoColor: {
    start: '#4f46e5',  // Indigo
    end: '#06b6d4',    // Luminous Cyan
  },

  /** Helper to get CSS linear-gradient string for HTML elements */
  getCssGradient: (angle = '90deg'): string => {
    if (BAR_GRADIENT_CONFIG.mode === 'three-color') {
      const { start, middle, end } = BAR_GRADIENT_CONFIG.threeColor;
      return `linear-gradient(${angle}, ${start} 0%, ${middle} 50%, ${end} 100%)`;
    }
    const { start, end } = BAR_GRADIENT_CONFIG.twoColor;
    return `linear-gradient(${angle}, ${start} 0%, ${end} 100%)`;
  },

  /**
   * Computes an exact interpolated hex color sampled from the vertical gradient
   * for a bar at index `index` out of `total` bars.
   */
  getBarColorAt: (index: number, total: number): string => {
    if (total <= 1) {
      return BAR_GRADIENT_CONFIG.mode === 'three-color'
        ? BAR_GRADIENT_CONFIG.threeColor.start
        : BAR_GRADIENT_CONFIG.twoColor.start;
    }

    const t = Math.max(0, Math.min(1, index / (total - 1)));

    const interpolate = (c1: string, c2: string, factor: number): string => {
      const int1 = parseInt(c1.replace('#', ''), 16);
      const int2 = parseInt(c2.replace('#', ''), 16);

      const r1 = (int1 >> 16) & 255;
      const g1 = (int1 >> 8) & 255;
      const b1 = int1 & 255;

      const r2 = (int2 >> 16) & 255;
      const g2 = (int2 >> 8) & 255;
      const b2 = int2 & 255;

      const r = Math.round(r1 + (r2 - r1) * factor);
      const g = Math.round(g1 + (g2 - g1) * factor);
      const b = Math.round(b1 + (b2 - b1) * factor);

      return `#${[r, g, b].map((x) => x.toString(16).padStart(2, '0')).join('')}`;
    };

    if (BAR_GRADIENT_CONFIG.mode === 'three-color') {
      const { start, middle, end } = BAR_GRADIENT_CONFIG.threeColor;
      if (t <= 0.5) {
        return interpolate(start, middle, t * 2);
      }
      return interpolate(middle, end, (t - 0.5) * 2);
    }

    const { start, end } = BAR_GRADIENT_CONFIG.twoColor;
    return interpolate(start, end, t);
  },
};

/**
 * Configuration options for the Pareto Latency vs Accuracy chart.
 * Allows toggling logarithmic distribution, label density, and optimal zone threshold.
 */
export const PARETO_CHART_CONFIG = {
  /** Default scale mode: 'log' prevents clumping, 'linear' shows raw proportional distance */
  defaultScale: 'log' as 'log' | 'linear',
  /** Default label density: 'frontier' (clean, only frontier points), 'hover' (only on hover), 'all' (collision-free) */
  defaultLabelMode: 'frontier' as 'frontier' | 'hover' | 'all',
  /** Optimal sweet spot thresholds */
  optimalZone: {
    maxLatencyMs: 2000,
    minAccuracy: 0.70,
  },
};

/**
 * Sanitize strings to make them safe for use in SVG id attributes and CSS url(#id).
 * Replaces spaces, dots, and non-alphanumeric characters with underscores.
 */
export function sanitizeSvgId(raw: string): string {
  return raw.replace(/[^a-zA-Z0-9_-]/g, '_');
}

/**
 * Configuration options for the Model Filter Bar.
 * Can be tweaked to adjust display density, badges, and default state.
 */
export const FILTER_BAR_CONFIG = {
  /** Use concise, streamlined model names in filter chips */
  compactLabels: true,
  /** Default visibility of the detailed chips row */
  defaultExpanded: true,
  /** Whether to show dataset count pill inside chips (redundant when dataset filter is visible) */
  showDatasetBadge: false,
  /** Whether to show verbose runtime badge inside chips (redundant with hardware card/presets) */
  showRuntimeBadge: false,
  /** Whether to show subtle icon indicator for thinking models */
  showThinkingIcon: true,
  /** Whether to show subtle icon indicator for cloud models */
  showCloudIcon: true,
};

/**
 * Formats a verbose model series string into a clean, concise chip label.
 * Removes redundant provider prefixes (e.g. "Korgis · ") while preserving distinction.
 */
export function formatCompactModelName(series: string): string {
  return series
    .replace(/^Korgis\s*·\s*/i, '')
    .replace(/^Jev\s*·\s*/i, 'Jev ')
    .replace(/Qwen3\.5/g, 'Qwen')
    .replace(/Nemotron Nano/g, 'Nemotron')
    .replace(/\(Thinking\)/g, '(Think)')
    .replace(/\s*·\s*/g, ' · ')
    .trim();
}

const seriesColorMap: Record<string, string> = {};

export function getSeriesColor(series: string, index: number = 0): string {
  if (seriesColorMap[series]) {
    return seriesColorMap[series];
  }
  const color = THEME.palette[index % THEME.palette.length];
  seriesColorMap[series] = color;
  return color;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms == null || isNaN(ms)) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function formatPct(val: number | null | undefined, decimals: number = 1): string {
  if (val == null || isNaN(val)) return '—';
  return `${(val * 100).toFixed(decimals)}%`;
}

export function formatMoney(val: number | null | undefined, digits: number = 2): string {
  if (val == null || isNaN(val)) return '—';
  if (val === 0) return '$0.00';
  if (val < 0.01) return `$${val.toFixed(4)}`;
  return `$${val.toFixed(digits)}`;
}

export interface ModelRuntimeInfo {
  type: 'local' | 'cloud' | 'native';
  label: string;
  shortLabel: string;
  badgeBg: string;
  badgeColor: string;
  badgeBorder: string;
  hardwareSummary: string;
  costBadge: string;
  isFree: boolean;
}

export function getModelRuntime(provider: string = '', series: string = ''): ModelRuntimeInfo {
  const p = (provider || '').toLowerCase();
  const s = (series || '').toLowerCase();

  if (p.includes('decisio') || s.includes('decisio')) {
    const usesMetal = s.includes('metal');
    return {
      type: 'local',
      label: usesMetal ? 'Apple M3 Pro (Metal)' : 'Apple M3 Pro (CPU)',
      shortLabel: usesMetal ? 'M3 Pro Metal' : 'M3 Pro CPU',
      badgeBg: '#fff7ed',
      badgeColor: '#9a3412',
      badgeBorder: '#fed7aa',
      hardwareSummary: usesMetal
        ? 'Apple M3 Pro · Metal GPU · 36 GB Unified RAM'
        : 'Apple M3 Pro · 4 CPU threads · 36 GB Unified RAM',
      costBadge: '$0.00 Free',
      isFree: true,
    };
  }

  if (p.includes('korgis') || s.includes('korgis') || s.includes('qwen') || s.includes('nemotron') || s.includes('minicpm')) {
    return {
      type: 'local',
      label: 'Apple M3 Pro (36GB Local)',
      shortLabel: 'M3 Pro Local',
      badgeBg: '#f0fdf4',
      badgeColor: '#166534',
      badgeBorder: '#bbf7d0',
      hardwareSummary: 'Apple M3 Pro · 11 Cores · 36 GB Unified RAM',
      costBadge: '$0.00 Free',
      isFree: true,
    };
  }

  if (p.includes('llm') || p.includes('openai') || s.includes('gpt') || s.includes('luna')) {
    return {
      type: 'cloud',
      label: 'Cloud API (OpenAI)',
      shortLabel: 'Cloud API',
      badgeBg: '#eef2ff',
      badgeColor: '#4338ca',
      badgeBorder: '#c7d2fe',
      hardwareSummary: 'OpenAI Remote API Endpoint',
      costBadge: 'Pay-per-token',
      isFree: false,
    };
  }

  // Jev / native router
  return {
    type: 'native',
    label: 'Native Router',
    shortLabel: 'Native',
    badgeBg: '#f8fafc',
    badgeColor: '#0f172a',
    badgeBorder: '#cbd5e1',
    hardwareSummary: 'Local Native Compiled Router',
    costBadge: 'Local Native',
    isFree: false,
  };
}
