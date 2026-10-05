import fs from 'node:fs';
import path from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

function devAnalyticsPlugin(): Plugin {
  return {
    name: 'dev-analytics-data',
    apply: 'serve',
    transformIndexHtml(html) {
      const dataDir = path.resolve(import.meta.dirname, '../results/analytics/dashboard');
      const overviewFile = path.join(dataDir, 'overview.json');
      if (!fs.existsSync(overviewFile)) {
        return html;
      }
      try {
        const overview = JSON.parse(fs.readFileSync(overviewFile, 'utf-8'));
        const capabilitiesDir = path.join(dataDir, 'capabilities');
        const capabilities: Record<string, unknown> = {};
        if (fs.existsSync(capabilitiesDir)) {
          for (const file of fs.readdirSync(capabilitiesDir)) {
            if (file.endsWith('.json')) {
              capabilities[file.replace('.json', '')] = JSON.parse(
                fs.readFileSync(path.join(capabilitiesDir, file), 'utf-8'),
              );
            }
          }
        }
        const modelsDir = path.join(dataDir, 'models');
        const models: Record<string, unknown> = {};
        if (fs.existsSync(modelsDir)) {
          for (const file of fs.readdirSync(modelsDir)) {
            if (file.endsWith('.json')) {
              models[file.replace('.json', '')] = JSON.parse(
                fs.readFileSync(path.join(modelsDir, file), 'utf-8'),
              );
            }
          }
        }
        const runsDir = path.join(dataDir, 'runs');
        const runs: Record<string, unknown> = {};
        if (fs.existsSync(runsDir)) {
          for (const file of fs.readdirSync(runsDir)) {
            if (file.endsWith('.json')) {
              runs[file.replace('.json', '')] = JSON.parse(
                fs.readFileSync(path.join(runsDir, file), 'utf-8'),
              );
            }
          }
        }
        const firstCap = Object.values(capabilities)[0] ?? null;
        const injection = `<script>
window.__MCB_OVERVIEW__ = ${JSON.stringify(overview)};
${firstCap ? `window.__MCB_CAPABILITY__ = ${JSON.stringify(firstCap)};` : ''}
window.__MCB_CAPABILITIES__ = ${JSON.stringify(capabilities)};
window.__MCB_MODELS__ = ${JSON.stringify(models)};
window.__MCB_RUNS__ = ${JSON.stringify(runs)};
</script>`;
        return html.replace('</head>', `${injection}\n</head>`);
      } catch (err) {
        console.warn('Failed to load dev analytics data, using fixtures:', err);
        return html;
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), viteSingleFile(), devAnalyticsPlugin()],
  build: {
    target: 'esnext',
    assetsInlineLimit: 100000000,
    chunkSizeWarningLimit: 100000000,
    cssCodeSplit: false,
    outDir: 'dist',
  },
});
