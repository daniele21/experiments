import overviewFixture from './data/overview.fixture.json';
import capabilityFixture from './data/structured-output.fixture.json';
import type {
  CapabilityPayload,
  ModelPayload,
  OverviewPayload,
  RunPayload,
} from './types';

declare global {
  interface Window {
    __MCB_OVERVIEW__?: OverviewPayload;
    __MCB_CAPABILITY__?: CapabilityPayload;
    __MCB_CAPABILITIES__?: Record<string, CapabilityPayload>;
    __MCB_MODELS__?: Record<string, ModelPayload>;
    __MCB_RUNS__?: Record<string, RunPayload>;
  }
}

export const overview =
  (window.__MCB_OVERVIEW__ ?? overviewFixture) as OverviewPayload;

export const capability =
  (window.__MCB_CAPABILITY__ ?? capabilityFixture) as CapabilityPayload;

export const capabilityPayloads: Record<string, CapabilityPayload> =
  window.__MCB_CAPABILITIES__ ?? {
    [capability.capability_id]: capability,
  };

export const modelPayloads = window.__MCB_MODELS__ ?? {};
export const runPayloads = window.__MCB_RUNS__ ?? {};
