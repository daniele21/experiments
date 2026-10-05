export function capabilityLabel(value: string): string {
  return value
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function percent(value: number | null | undefined): string {
  return value == null ? '—' : (value * 100).toFixed(1) + '%';
}

export function score(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(1);
}

export function points(value: number | null | undefined): string {
  if (value == null) return '—';
  const sign = value > 0 ? '+' : '';
  return sign + (value * 100).toFixed(1) + ' pp';
}

export function milliseconds(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value >= 1000) return (value / 1000).toFixed(2) + ' s';
  return Math.round(value) + ' ms';
}

export function usd(value: number | null | undefined): string {
  if (value == null) return '—';
  if (value < 0.01) return '$' + value.toFixed(4);
  return '$' + value.toFixed(2);
}

export function bytes(value: number | null | undefined): string {
  if (value == null) return '—';
  const gb = value / (1024 ** 3);
  if (gb >= 1) return gb.toFixed(1) + ' GB';
  return (value / (1024 ** 2)).toFixed(0) + ' MB';
}

export function cpu(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(0) + '%';
}

export function compactDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat('en', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}
