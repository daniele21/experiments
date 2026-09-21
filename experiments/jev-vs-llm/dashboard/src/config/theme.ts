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
};

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
