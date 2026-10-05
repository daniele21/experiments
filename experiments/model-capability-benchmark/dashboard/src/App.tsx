import type { ReactNode } from 'react';
import { capabilityPayloads } from './data';
import { usePathname } from './router';
import { Shell } from './components/Shell';
import { OverviewPage } from './pages/OverviewPage';
import {
  CapabilityPage,
  ComparePage,
  DatasetPage,
  DisagreementsPage,
  ModelPage,
  ModelsPage,
  PlaceholderPage,
  RunPage,
  RunsPage,
  SharePage,
} from './pages/ExplorerPages';

export function App() {
  const pathname = usePathname();
  const disagreementMatch = pathname.match(
    /^\/capabilities\/([^/]+)\/disagreements$/,
  );
  const capabilityMatch = pathname.match(/^\/capabilities\/([^/]+)$/);
  const modelMatch = pathname.match(/^\/models\/([^/]+)$/);
  const datasetMatch = pathname.match(/^\/datasets\/([^/]+)$/);
  const runMatch = pathname.match(/^\/runs\/([^/]+)$/);

  let page: ReactNode;
  if (pathname === '/' || pathname === '/overview') {
    page = <OverviewPage />;
  } else if (pathname === '/models') {
    page = <ModelsPage />;
  } else if (modelMatch) {
    page = <ModelPage signature={decodeURIComponent(modelMatch[1])} />;
  } else if (disagreementMatch) {
    const capabilityId = decodeURIComponent(disagreementMatch[1]);
    const payload = capabilityPayloads[capabilityId];
    page = payload ? (
      <DisagreementsPage payload={payload} />
    ) : (
      <PlaceholderPage title="Capability not found" />
    );
  } else if (capabilityMatch) {
    const capabilityId = decodeURIComponent(capabilityMatch[1]);
    const payload = capabilityPayloads[capabilityId];
    page = payload ? (
      <CapabilityPage payload={payload} />
    ) : (
      <PlaceholderPage title="Capability not found" />
    );
  } else if (datasetMatch) {
    page = <DatasetPage datasetId={decodeURIComponent(datasetMatch[1])} />;
  } else if (pathname === '/compare') {
    page = <ComparePage />;
  } else if (pathname === '/runs') {
    page = <RunsPage />;
  } else if (runMatch) {
    page = <RunPage runId={decodeURIComponent(runMatch[1])} />;
  } else if (pathname === '/share') {
    page = <SharePage />;
  } else {
    page = <PlaceholderPage title="Not found" />;
  }

  return <Shell>{page}</Shell>;
}
