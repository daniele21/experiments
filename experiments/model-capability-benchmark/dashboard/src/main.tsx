import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { parseDashboardBundle } from './dashboardBundle';
import './styles.css';

async function start() {
  if (window.__MCB_DATA_URL__) {
    const response = await fetch(window.__MCB_DATA_URL__, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Dashboard data: HTTP ${response.status}`);
    window.__MCB_DASHBOARD_DATA__ = parseDashboardBundle(await response.json());
  }
  // Import after loading data: every route uses the same complete snapshot.
  const { App } = await import('./App');
  createRoot(document.getElementById('root')!).render(
    <StrictMode><App /></StrictMode>,
  );
}

start().catch((error: unknown) => {
  const root = document.getElementById('root')!;
  root.setAttribute('role', 'alert');
  root.textContent = error instanceof Error ? error.message : 'Unable to load dashboard data';
});
