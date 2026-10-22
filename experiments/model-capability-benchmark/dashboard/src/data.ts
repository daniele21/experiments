import overviewFixture from './data/overview.fixture.json';
import capabilityFixture from './data/structured-output.fixture.json';
import type {
  CapabilityPayload,
  DashboardBundle,
  ModelPayload,
  OverviewPayload,
  RunPayload,
} from './types';

declare global {
  interface Window {
    __MCB_DATA_URL__?: string;
    __MCB_DASHBOARD_DATA__?: DashboardBundle;
    __MCB_OVERVIEW__?: OverviewPayload;
    __MCB_CAPABILITY__?: CapabilityPayload;
    __MCB_CAPABILITIES__?: Record<string, CapabilityPayload>;
    __MCB_MODELS__?: Record<string, ModelPayload>;
    __MCB_RUNS__?: Record<string, RunPayload>;
  }
}

export const overview =
  (window.__MCB_DASHBOARD_DATA__?.overview ?? window.__MCB_OVERVIEW__ ?? overviewFixture) as OverviewPayload;

export const capability =
  (window.__MCB_DASHBOARD_DATA__?.capabilities['structured-output']
    ?? Object.values(window.__MCB_DASHBOARD_DATA__?.capabilities ?? {})[0]
    ?? window.__MCB_CAPABILITY__ ?? capabilityFixture) as CapabilityPayload;

export const capabilityPayloads: Record<string, CapabilityPayload> =
  window.__MCB_DASHBOARD_DATA__?.capabilities ?? window.__MCB_CAPABILITIES__ ?? {
    [capability.capability_id]: capability,
  };

export const modelPayloads = window.__MCB_DASHBOARD_DATA__?.models ?? window.__MCB_MODELS__ ?? {};
export const runPayloads = window.__MCB_DASHBOARD_DATA__?.runs ?? window.__MCB_RUNS__ ?? {};
