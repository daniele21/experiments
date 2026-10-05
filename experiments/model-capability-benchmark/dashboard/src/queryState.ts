export function currentQuery(): URLSearchParams {
  if (window.location.protocol === 'file:' && window.location.hash.includes('?')) {
    return new URLSearchParams(window.location.hash.split('?')[1] ?? '');
  }
  return new URLSearchParams(window.location.search);
}

export function updateQuery(
  updates: Record<string, string | null>,
  replace = true,
): void {
  const params = currentQuery();
  Object.entries(updates).forEach(([key, value]) => {
    if (value == null || value === '') params.delete(key);
    else params.set(key, value);
  });

  const query = params.toString();
  if (window.location.protocol === 'file:') {
    const route = (window.location.hash.slice(1).split('?')[0] || '/overview');
    const next = '#' + route + (query ? '?' + query : '');
    if (replace) window.history.replaceState({}, '', next);
    else window.location.hash = route + (query ? '?' + query : '');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    return;
  }

  const next = window.location.pathname + (query ? '?' + query : '');
  if (replace) window.history.replaceState({}, '', next);
  else window.history.pushState({}, '', next);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
