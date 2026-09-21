import React from 'react';
import type { BenchmarkMetadata, PricingInfo, OverviewRow } from '../../types/benchmark';

interface RunDetailsTabProps {
  metadata: BenchmarkMetadata;
  pricing: PricingInfo;
  overview: OverviewRow[];
}

export const RunDetailsTab: React.FC<RunDetailsTabProps> = ({ metadata, pricing, overview }) => {
  const pricingRows = Object.entries(pricing.prices_per_million_tokens || {});

  return (
    <div>
      {/* 1. Execution Context */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Run Context &amp; Environment</h3>
          <p className="card-subtitle">
            Parameters and execution environment for the evaluated benchmark group.
          </p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          <div style={{ background: 'var(--surface-alt)', padding: '14px', borderRadius: 'var(--radius-md)' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Run Group</span>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: 600, marginTop: '4px' }}>
              {metadata.run_group}
            </div>
          </div>
          <div style={{ background: 'var(--surface-alt)', padding: '14px', borderRadius: 'var(--radius-md)' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Suite</span>
            <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '4px' }}>
              {metadata.suite}
            </div>
          </div>
          <div style={{ background: 'var(--surface-alt)', padding: '14px', borderRadius: 'var(--radius-md)' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Runner Location</span>
            <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '4px' }}>
              {metadata.runner_location}
            </div>
          </div>
          <div style={{ background: 'var(--surface-alt)', padding: '14px', borderRadius: 'var(--radius-md)' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Total Evaluated Rows</span>
            <div style={{ fontSize: '13px', fontWeight: 600, marginTop: '4px' }}>
              {metadata.total_rows}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Pricing Snapshot */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Token Pricing Snapshot ({pricing.as_of})</h3>
          <p className="card-subtitle">
            Standard provider pricing in USD per 1M tokens used for cloud API cost comparisons. Local models have $0 provider token charges.
          </p>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Input / 1M</th>
              <th>Cached Input / 1M</th>
              <th>Output / 1M</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {pricingRows.map(([model, p]) => (
              <tr key={model}>
                <td><strong>{model}</strong></td>
                <td>${p.input}</td>
                <td>{p.cached_input != null ? `$${p.cached_input}` : '—'}</td>
                <td>${p.output}</td>
                <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{p.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 3. Aggregate Overview Table */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Aggregate Summary Metrics</h3>
          <p className="card-subtitle">
            Summary numbers across all models for verification and auditing.
          </p>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Accuracy</th>
              <th>p50 Latency</th>
              <th>p95 Latency</th>
              <th>Valid Rate</th>
              <th>Requests</th>
            </tr>
          </thead>
          <tbody>
            {overview.map((row) => (
              <tr key={row.series}>
                <td><strong>{row.series}</strong></td>
                <td>{(row.accuracy * 100).toFixed(1)}%</td>
                <td>{Math.round(row.latency_p50_ms)} ms</td>
                <td>{Math.round(row.latency_p95_ms)} ms</td>
                <td>{(row.valid_rate * 100).toFixed(1)}%</td>
                <td>{row.requests}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
