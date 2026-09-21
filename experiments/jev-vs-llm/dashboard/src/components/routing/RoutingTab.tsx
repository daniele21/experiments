import React, { useState } from 'react';
import type { RoutingData } from '../../types/benchmark';
import { Search, ChevronDown, ChevronRight, AlertCircle, DollarSign } from 'lucide-react';

interface RoutingTabProps {
  data: RoutingData;
  selectedSeries: Set<string>;
}

export const RoutingTab: React.FC<RoutingTabProps> = ({ data, selectedSeries }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [openCases, setOpenCases] = useState<Set<string>>(new Set());

  const toggleCase = (id: string) => {
    setOpenCases((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filteredCases = data.cases.filter((c) => {
    if (!selectedSeries.has(c.series)) return false;
    if (statusFilter !== 'all' && c.status.toLowerCase() !== statusFilter.toLowerCase()) return false;
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      c.case_id.toLowerCase().includes(q) ||
      c.input_state.toLowerCase().includes(q) ||
      c.expected.toLowerCase().includes(q) ||
      c.actual.toLowerCase().includes(q)
    );
  });

  const visibleConfusions = data.confusions.filter((c) => selectedSeries.has(c.series));
  const visiblePerClass = data.per_class.filter((c) => selectedSeries.has(c.series));
  const visibleErrors = data.errors.filter((e) => selectedSeries.has(e.series));

  return (
    <div>
      {/* 1. Confusion Pairs */}
      {visibleConfusions.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Most frequent confusion pairs</h3>
            <p className="card-subtitle">
              Frequent misclassifications where models selected an alternative class instead of the labelled target intent.
            </p>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Expected → Predicted Intent</th>
                <th style={{ width: '100px' }}>Errors</th>
              </tr>
            </thead>
            <tbody>
              {visibleConfusions.slice(0, 12).map((conf, idx) => (
                <tr key={`${conf.series}-${conf.pair}-${idx}`}>
                  <td><strong>{conf.series}</strong></td>
                  <td><code>{conf.pair}</code></td>
                  <td>
                    <span className="delta-badge far">{conf.count}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 2. Routing API Cost summary */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <DollarSign size={18} style={{ color: 'var(--success)' }} />
            <h3 className="card-title">Routing API cost</h3>
          </div>
          <p className="card-subtitle">
            Estimated list-price cost for 1,000 routing requests based on input and output token consumption.
          </p>
        </div>
        <div style={{ padding: '12px 16px', background: 'var(--surface-alt)', borderRadius: 'var(--radius-md)', fontSize: '13px', color: 'var(--text-muted)' }}>
          All evaluated local models executed through Korgis with zero provider API fee ($0.00 / 1k requests). Cloud models are billed by token consumption.
        </div>
      </div>

      {/* 3. Per-Class Accuracy Table */}
      {visiblePerClass.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Per-class breakdown</h3>
            <p className="card-subtitle">
              Accuracy across evaluated classes and the most common incorrect prediction for each.
            </p>
          </div>
          <div style={{ maxHeight: '380px', overflowY: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Intent Class</th>
                  <th style={{ width: '90px' }}>Cases</th>
                  <th style={{ width: '110px' }}>Accuracy</th>
                  <th>Top Wrong Output</th>
                </tr>
              </thead>
              <tbody>
                {visiblePerClass.slice(0, 50).map((row, idx) => (
                  <tr key={`${row.series}-${row.class}-${idx}`}>
                    <td>{row.series}</td>
                    <td><code>{row.class}</code></td>
                    <td>{row.cases}</td>
                    <td>
                      <span style={{ fontWeight: 700, color: row.accuracy >= 0.8 ? 'var(--success)' : row.accuracy >= 0.5 ? 'var(--warning)' : 'var(--danger)' }}>
                        {(row.accuracy * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td><code>{row.top_wrong}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 4. Case Explorer */}
      <div className="card explorer-card">
        <div className="card-header">
          <h3 className="card-title">Routing cases</h3>
          <p className="card-subtitle">
            Search inputs, expected intents, and actual model predictions. Expand any case to inspect decision traces.
          </p>
        </div>

        <div className="explorer-toolbar">
          <div className="search-input-wrapper">
            <Search size={15} className="search-icon" />
            <input
              type="text"
              className="search-input case-search"
              placeholder="Search by input query, intent, or case ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Status:</span>
            {['all', 'correct', 'wrong', 'invalid'].map((st) => (
              <button
                key={st}
                className={`tab-btn ${statusFilter === st ? 'active' : ''}`}
                style={{ padding: '4px 10px', fontSize: '12px' }}
                onClick={() => setStatusFilter(st)}
              >
                {st.toUpperCase()}
              </button>
            ))}
            <span className="case-count-text" style={{ marginLeft: '8px' }}>
              Showing {filteredCases.length} cases
            </span>
          </div>
        </div>

        <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
          {filteredCases.map((c) => {
            const isOpen = openCases.has(c.case_id + c.series);
            return (
              <div key={c.case_id + c.series} className="case-card">
                <div
                  className="case-summary"
                  onClick={() => toggleCase(c.case_id + c.series)}
                >
                  {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  <span className={`case-status-dot ${c.status_class}`} />
                  <span className="case-id-text">{c.case_id}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>{c.series}</span>
                  <span
                    className={`delta-badge ${
                      c.status === 'Correct' ? 'leader' : 'far'
                    }`}
                    style={{ fontSize: '11px', padding: '1px 6px' }}
                  >
                    {c.status}
                  </span>
                  <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-muted)' }}>
                    {Math.round(c.latency_ms)} ms
                  </span>
                  <span style={{ fontSize: '12px' }}>
                    Output: <strong>{c.actual || '—'}</strong> / Expected: {c.expected}
                  </span>
                </div>

                {isOpen && (
                  <div className="case-details-body">
                    <div style={{ marginBottom: '8px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                      Query Input
                    </div>
                    <div className="case-input-box">
                      {c.input_state}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px', marginTop: '12px' }}>
                      <div style={{ background: 'var(--surface)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Expected Class:</span>
                        <div style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{c.expected}</div>
                      </div>
                      <div style={{ background: 'var(--surface)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Model Predicted:</span>
                        <div style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: c.correct ? 'var(--success)' : 'var(--danger)' }}>
                          {c.actual || 'None'}
                        </div>
                      </div>
                      <div style={{ background: 'var(--surface)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Latency:</span>
                        <div style={{ fontWeight: 600 }}>{Math.round(c.latency_ms)} ms</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. Error explorer */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle size={18} style={{ color: 'var(--warning)' }} />
            <h3 className="card-title">Error explorer</h3>
          </div>
          <p className="card-subtitle">
            Schema validation, provider failures, and invalid format outputs.
          </p>
        </div>
        {visibleErrors.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Case ID</th>
                <th>Question</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {visibleErrors.map((err, idx) => (
                <tr key={idx}>
                  <td><strong>{err.series}</strong></td>
                  <td><code>{err.case_id}</code></td>
                  <td><code>{err.question_id}</code></td>
                  <td style={{ color: 'var(--danger)' }}>{err.error || 'Invalid format'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ padding: '16px', color: 'var(--text-muted)', fontSize: '13px' }}>
            No schema or provider failures detected in this experiment run.
          </div>
        )}
      </div>
    </div>
  );
};
