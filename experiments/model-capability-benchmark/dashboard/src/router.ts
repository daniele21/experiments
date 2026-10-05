import { useEffect, useState } from 'react';

function currentRoute(): string {
  if (window.location.protocol === 'file:' && window.location.hash) {
    return window.location.hash.slice(1);
  }
  const pathname = window.location.pathname;
  if (window.location.protocol === 'file:' || pathname.endsWith('.html')) {
    return '/overview';
  }
  return pathname;
}

export function usePathname(): string {
  const [pathname, setPathname] = useState(currentRoute);

  useEffect(() => {
    const update = () => setPathname(currentRoute());
    window.addEventListener('popstate', update);
    window.addEventListener('hashchange', update);
    return () => {
      window.removeEventListener('popstate', update);
      window.removeEventListener('hashchange', update);
    };
  }, []);

  return pathname;
}

export function navigate(path: string): void {
  if (window.location.protocol === 'file:') {
    window.location.hash = path;
    return;
  }
  if (window.location.pathname === path) return;
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
