import React, { useState, useEffect, useMemo } from 'react';
import type { BenchmarkPayload } from './types/benchmark';
import staticData from './data/benchmark_data.json';
import { Header } from './components/layout/Header';
import { NavigationTabs } from './components/layout/NavigationTabs';
import type { TabKey } from './components/layout/NavigationTabs';
import { ModelFilterBar } from './components/layout/ModelFilterBar';
import { DatasetFilterBar, type DatasetFilterKey } from './components/layout/DatasetFilterBar';
import { KpiCards } from './components/overview/KpiCards';
import { Leaderboard } from './components/overview/Leaderboard';
import { AccuracyGapChart } from './components/overview/AccuracyGapChart';
import { ParetoTradeoffChart } from './components/overview/ParetoTradeoffChart';
import { LatencyComparisonChart } from './components/overview/LatencyComparisonChart';
import { LocalEfficiencyCard } from './components/overview/LocalEfficiencyCard';
import { CostAccuracyChart } from './components/overview/CostAccuracyChart';
import { ExecutiveVerdictBanner } from './components/overview/ExecutiveVerdictBanner';
import { RoutingTab } from './components/routing/RoutingTab';
import { UnrunExperimentView } from './components/experiment/UnrunExperimentView';
import { RunDetailsTab } from './components/details/RunDetailsTab';
import { getModelRuntime } from './config/theme';

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

  // Active dataset tier filter (all, public, smoke)
  const [activeDataset, setActiveDataset] = useState<DatasetFilterKey>('all');

  // Selected models filter
  const [selectedSeries, setSelectedSeries] = useState<Set<string>>(() => {
    return new Set(data.models.map((m) => m.series));
  });

  // Compute dataset counts
  const datasetCounts = useMemo(() => {
    const pub = data.leaderboard.filter((m) => m.dataset === 'public').length;
    const smk = data.leaderboard.filter((m) => m.dataset === 'smoke').length;
    return {
      all: data.leaderboard.length,
      public: pub,
      smoke: smk,
    };
  }, [data.leaderboard]);

  // Models filtered for the model chips bar
  const activeModels = useMemo(() => {
    if (activeDataset === 'all') return data.models;
    return data.models.filter((m) => m.dataset === activeDataset);
  }, [data.models, activeDataset]);

  // Frontier view state ('both' | 'latency' | 'cost')
  const [frontierView, setFrontierView] = useState<'both' | 'latency' | 'cost'>('both');

  // Leaderboard filtered by dataset
  const filteredLeaderboard = useMemo(() => {
    if (activeDataset === 'all') return data.leaderboard;
    return data.leaderboard.filter((m) => m.dataset === activeDataset);
  }, [data.leaderboard, activeDataset]);

  // Overview filtered by dataset
  const filteredOverview = useMemo(() => {
    if (activeDataset === 'all') return data.overview;
    return data.overview.filter((m) => m.dataset === activeDataset);
  }, [data.overview, activeDataset]);

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

  const handleSetPreset = (preset: 'all' | 'local' | 'non-local') => {
    if (preset === 'all') {
      setSelectedSeries(new Set(data.models.map((m) => m.series)));
    } else if (preset === 'local') {
      const local = data.models
        .filter((m) => getModelRuntime(m.provider, m.series).type === 'local')
        .map((m) => m.series);
      if (local.length > 0) setSelectedSeries(new Set(local));
    } else {
      const nonLocal = data.models
        .filter((m) => getModelRuntime(m.provider, m.series).type !== 'local')
        .map((m) => m.series);
      if (nonLocal.length > 0) setSelectedSeries(new Set(nonLocal));
    }
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

      {/* 2. Sticky Toolbar: Navigation Tabs, Dataset Selector & Model Filter Chips */}
      <div className="toolbar-container">
        <div className="toolbar-content">
          <NavigationTabs
            activeTab={activeTab}
            onSelectTab={handleSelectTab}
            experiments={data.experiments}
          />
          <DatasetFilterBar
            activeDataset={activeDataset}
            onSelectDataset={setActiveDataset}
            counts={datasetCounts}
          />
          <ModelFilterBar
            models={activeModels}
            selectedSeries={selectedSeries}
            onToggleSeries={toggleSeries}
            onSetPreset={handleSetPreset}
          />
        </div>
      </div>

      {/* 3. Tab Contents */}
      {activeTab === 'overview' && (
        <main className="overview-main">
          {/* Level 1: Executive Verdict & Top-Level Takeaways */}
          <section className="dashboard-section">
            <ExecutiveVerdictBanner leaderboard={filteredLeaderboard} metadata={data.metadata} />
            <KpiCards data={data.kpi_cards} hardware={data.metadata.hardware} />
          </section>

          {/* Level 2: Core Benchmark Leaderboard & Gap Analysis */}
          <section className="dashboard-section">
            <Leaderboard
              entries={filteredLeaderboard}
              selectedSeries={selectedSeries}
              activeDataset={activeDataset}
            />
            <AccuracyGapChart entries={filteredLeaderboard} selectedSeries={selectedSeries} />
          </section>

          {/* Level 3: Strategic Decision Frontiers (Speed & Cost Pareto Frameworks) */}
          <section className="dashboard-section">
            <div className="section-intro-row">
              <div className="section-intro" style={{ marginBottom: 0 }}>
                <span className="section-step-badge">★ Core Decision Frameworks</span>
                <h2 className="section-headline">Performance &amp; Cost Frontiers</h2>
                <p className="section-subheadline">
                  The primary strategic decision matrix: identifying Pareto-optimal models across response latency and token economics.
                </p>
              </div>

              {/* Frontier View Switcher */}
              <div className="frontier-view-control">
                <button
                  type="button"
                  className={`frontier-view-btn ${frontierView === 'both' ? 'active' : ''}`}
                  onClick={() => setFrontierView('both')}
                  title="View both Latency and Cost Frontiers"
                >
                  <span>🔲 Dual View (Both)</span>
                </button>
                <button
                  type="button"
                  className={`frontier-view-btn ${frontierView === 'latency' ? 'active' : ''}`}
                  onClick={() => setFrontierView('latency')}
                  title="Focus on Latency vs Accuracy Frontier"
                >
                  <span>⚡ Latency vs Accuracy</span>
                </button>
                <button
                  type="button"
                  className={`frontier-view-btn ${frontierView === 'cost' ? 'active' : ''}`}
                  onClick={() => setFrontierView('cost')}
                  title="Focus on Cost vs Accuracy Frontier"
                >
                  <span>💰 Cost vs Accuracy</span>
                </button>
              </div>
            </div>

            {/* Frontier Hero Display */}
            <div className="frontier-hero-stack">
              {(frontierView === 'both' || frontierView === 'latency') && (
                <ParetoTradeoffChart entries={filteredLeaderboard} selectedSeries={selectedSeries} />
              )}
              {(frontierView === 'both' || frontierView === 'cost') && (
                <CostAccuracyChart overview={filteredOverview} selectedSeries={selectedSeries} />
              )}
            </div>

            {/* Detailed Diagnostic Latency Breakdown */}
            <div style={{ marginTop: '24px' }}>
              <LatencyComparisonChart entries={filteredLeaderboard} selectedSeries={selectedSeries} />
            </div>
          </section>

          {/* Level 4: Hardware Specifications & Local Economics */}
          <section className="dashboard-section">
            <LocalEfficiencyCard entries={filteredLeaderboard} metadata={data.metadata} />
          </section>
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
