import React, { useState, useEffect, useMemo } from 'react';
import type { BenchmarkPayload } from './types/benchmark';
import staticData from './data/benchmark_data.json';
import { Header } from './components/layout/Header';
import { NavigationTabs } from './components/layout/NavigationTabs';
import type { TabKey } from './components/layout/NavigationTabs';
import { ModelFilterBar } from './components/layout/ModelFilterBar';
import { KpiCards } from './components/overview/KpiCards';
import { Leaderboard } from './components/overview/Leaderboard';
import { AccuracyGapChart } from './components/overview/AccuracyGapChart';
import { ParetoTradeoffChart } from './components/overview/ParetoTradeoffChart';
import { LatencyComparisonChart } from './components/overview/LatencyComparisonChart';
import { LocalEfficiencyCard } from './components/overview/LocalEfficiencyCard';
import { RoutingTab } from './components/routing/RoutingTab';
import { UnrunExperimentView } from './components/experiment/UnrunExperimentView';
import { RunDetailsTab } from './components/details/RunDetailsTab';
import { AlertCircle } from 'lucide-react';

declare global {
  interface Window {
    __BENCHMARK_DATA__?: BenchmarkPayload;
  }
}

export const App: React.FC = () => {
  // Load data from window injection if available, otherwise use static imported JSON
  const data: BenchmarkPayload = useMemo(() => {
    if (typeof window !== 'undefined' && window.__BENCHMARK_DATA__) {
      return window.__BENCHMARK_DATA__;
    }
    return staticData as unknown as BenchmarkPayload;
  }, []);

  // Hash navigation (sync active tab with window.location.hash)
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    if (typeof window !== 'undefined' && window.location.hash) {
      const hash = window.location.hash.replace('#', '') as TabKey;
      if (['overview', 'routing', 'calibration', 'scaling', 'workflow', 'agent', 'details'].includes(hash)) {
        return hash;
      }
    }
    return 'overview';
  });

  const handleSelectTab = (tab: TabKey) => {
    setActiveTab(tab);
    if (typeof window !== 'undefined') {
      window.location.hash = tab;
    }
  };

  // Selected models filter
  const [selectedSeries, setSelectedSeries] = useState<Set<string>>(() => {
    return new Set(data.models.map((m) => m.series));
  });

  const toggleSeries = (series: string) => {
    setSelectedSeries((prev) => {
      const next = new Set(prev);
      if (next.has(series)) {
        if (next.size > 1) {
          next.delete(series);
        }
      } else {
        next.add(series);
      }
      return next;
    });
  };

  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash.replace('#', '') as TabKey;
      if (['overview', 'routing', 'calibration', 'scaling', 'workflow', 'agent', 'details'].includes(hash)) {
        setActiveTab(hash);
      }
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  return (
    <div className="app-shell">
      {/* 1. Top Header */}
      <Header metadata={data.metadata} />

      {/* 2. Sticky Toolbar: Navigation Tabs & Model Filter Chips */}
      <div className="toolbar-container">
        <div className="toolbar-content">
          <NavigationTabs
            activeTab={activeTab}
            onSelectTab={handleSelectTab}
            experiments={data.experiments}
          />
          <ModelFilterBar
            models={data.models}
            selectedSeries={selectedSeries}
            onToggleSeries={toggleSeries}
          />
        </div>
      </div>

      {/* Notice Banner */}
      <div className="notice-banner">
        <AlertCircle size={18} style={{ flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong>Local Execution Note:</strong> Evaluated models run locally via the Korgis inference engine with zero cloud token charges. Accuracy reflects deterministic classification correctness on 77-way intent queries; latency measures client roundtrip time on host hardware.
        </div>
      </div>

      {/* 3. Tab Contents */}
      {activeTab === 'overview' && (
        <main>
          <KpiCards data={data.kpi_cards} />
          <Leaderboard entries={data.leaderboard} selectedSeries={selectedSeries} />
          <AccuracyGapChart entries={data.leaderboard} selectedSeries={selectedSeries} />
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: '20px' }}>
            <ParetoTradeoffChart entries={data.leaderboard} selectedSeries={selectedSeries} />
            <LatencyComparisonChart entries={data.leaderboard} selectedSeries={selectedSeries} />
          </div>
          <LocalEfficiencyCard entries={data.leaderboard} />
        </main>
      )}

      {activeTab === 'routing' && (
        <main>
          {data.experiments.routing?.has_data ? (
            <RoutingTab data={data.routing} selectedSeries={selectedSeries} />
          ) : (
            <UnrunExperimentView status={data.experiments.routing} />
          )}
        </main>
      )}

      {activeTab === 'calibration' && (
        <main>
          {data.experiments.calibration?.has_data ? (
            <div>Calibration data view</div>
          ) : (
            <UnrunExperimentView status={data.experiments.calibration} />
          )}
        </main>
      )}

      {activeTab === 'scaling' && (
        <main>
          {data.experiments.scaling?.has_data ? (
            <div>Scaling data view</div>
          ) : (
            <UnrunExperimentView status={data.experiments.scaling} />
          )}
        </main>
      )}

      {activeTab === 'workflow' && (
        <main>
          {data.experiments.workflow?.has_data ? (
            <div>Workflow data view</div>
          ) : (
            <UnrunExperimentView status={data.experiments.workflow} />
          )}
        </main>
      )}

      {activeTab === 'agent' && (
        <main>
          {data.experiments.agent?.has_data ? (
            <div>Agent data view</div>
          ) : (
            <UnrunExperimentView status={data.experiments.agent} />
          )}
        </main>
      )}

      {activeTab === 'details' && (
        <main>
          <RunDetailsTab
            metadata={data.metadata}
            pricing={data.pricing}
            overview={data.overview}
          />
        </main>
      )}
    </div>
  );
};
