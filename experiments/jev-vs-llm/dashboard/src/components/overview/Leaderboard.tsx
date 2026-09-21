import React from 'react';
import type { LeaderboardEntry } from '../../types/benchmark';
import { getSeriesColor, getModelRuntime } from '../../config/theme';
import { Cpu, Cloud, Zap, Database } from 'lucide-react';

interface LeaderboardProps {
  entries: LeaderboardEntry[];
  selectedSeries: Set<string>;
  activeDataset?: 'all' | 'public' | 'smoke';
}

export const Leaderboard: React.FC<LeaderboardProps> = ({
  entries,
  selectedSeries,
  activeDataset = 'all',
}) => {
  // Filter by active dataset tier first
  const datasetFiltered = entries.filter((e) => {
    if (activeDataset === 'all') return true;
    return e.dataset === activeDataset;
  });

  // Filter by user's selected series
  const visibleEntries = datasetFiltered.filter((e) =>
    selectedSeries.has(e.series) || (e.series_id && selectedSeries.has(e.series_id))
  );

  const leaderAcc = visibleEntries.length > 0 ? visibleEntries[0].accuracy : 1.0;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title-row">
          <h2 className="card-title">Model Performance Leaderboard</h2>
          <span className="section-pill">
            Showing {visibleEntries.length} of {entries.length} Models
          </span>
        </div>
        <p className="card-subtitle">
          Side-by-side gap analysis ranked by intent classification correctness. Delta shows the
          accuracy difference relative to the top-performing model. Host execution environment is
          explicitly indicated for local Apple Silicon models.
        </p>
      </div>

      <div className="leaderboard-container">
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '70px' }}>Rank</th>
              <th style={{ minWidth: '240px' }}>Model &amp; Runtime</th>
              <th style={{ minWidth: '200px' }}>Accuracy</th>
              <th style={{ width: '120px' }}>Gap vs Top</th>
              <th style={{ minWidth: '150px' }}>Latency (p50)</th>
              <th style={{ width: '110px' }}>Validity</th>
              <th>Highlights</th>
            </tr>
          </thead>
          <tbody>
            {visibleEntries.map((entry, idx) => {
              const color = getSeriesColor(entry.series, idx);
              const runtime = getModelRuntime(entry.provider, entry.series);
              const isFilteredDataset = activeDataset !== 'all';
              const displayRank = isFilteredDataset ? idx + 1 : entry.rank;
              const displayMedal = isFilteredDataset
                ? idx === 0
                  ? '🥇'
                  : idx === 1
                  ? '🥈'
                  : idx === 2
                  ? '🥉'
                  : `#${idx + 1}`
                : entry.medal;

              const gapPts = entry.accuracy - leaderAcc;
              const deltaStr = isFilteredDataset
                ? idx === 0
                  ? 'Leader'
                  : `${gapPts >= 0 ? '+' : ''}${(gapPts * 100).toFixed(1)}%`
                : entry.delta_str;
              const deltaClass = isFilteredDataset
                ? idx === 0
                  ? 'leader'
                  : Math.abs(gapPts * 100) < 8.0
                  ? 'close'
                  : Math.abs(gapPts * 100) < 20.0
                  ? 'moderate'
                  : 'far'
                : entry.delta_class;

              const rowKey = entry.series_id || `${entry.series}_${entry.dataset || 'ds'}_${idx}`;

              return (
                <tr key={rowKey}>
                  <td>
                    <div className="rank-cell">
                      <span className="medal-icon">{displayMedal}</span>
                      <span>#{displayRank}</span>
                    </div>
                  </td>

                  <td>
                    <div className="model-cell">
                      <div className="model-name-line">
                        <span className="model-name-text">{entry.series}</span>
                      </div>
                      <div className="model-tags">
                        {/* Dataset Tier Badge */}
                        {entry.dataset === 'public' ? (
                          <span
                            className="tag-badge dataset-tag dataset-tag-public"
                            title="Evaluated on 77-case public Banking77 benchmark dataset"
                          >
                            <Database size={10} style={{ marginRight: '3px' }} />
                            <span>Banking77 (77)</span>
                          </span>
                        ) : (
                          <span
                            className="tag-badge dataset-tag dataset-tag-smoke"
                            title="Evaluated on 24-case local synthetic benchmark dataset"
                          >
                            <Zap size={10} style={{ marginRight: '3px' }} />
                            <span>Smoke (24)</span>
                          </span>
                        )}

                        {/* Thinking Mode Tag */}
                        {entry.thinking_mode === 'on' && (
                          <span
                            className="tag-badge thinking-tag thinking-tag-on"
                            title="Thinking mode active: reasoning traces generated before decision"
                          >
                            🧠 Think: ON
                          </span>
                        )}

                        {runtime.type === 'local' ? (
                          <span className="tag-badge env-tag env-tag-local" title="Executed on Apple Silicon M3 Pro with 36GB RAM">
                            <Cpu size={11} style={{ marginRight: '3px' }} />
                            <span>Apple M3 Pro · 36GB Local</span>
                          </span>
                        ) : runtime.type === 'cloud' ? (
                          <span className="tag-badge env-tag env-tag-cloud" title="Executed via OpenAI Cloud API">
                            <Cloud size={11} style={{ marginRight: '3px' }} />
                            <span>Cloud API (OpenAI)</span>
                          </span>
                        ) : (
                          <span className="tag-badge env-tag env-tag-native" title="Compiled Native Router">
                            <Zap size={11} style={{ marginRight: '3px' }} />
                            <span>Compiled Native</span>
                          </span>
                        )}

                        {entry.quant_label && (
                          <span className="tag-badge quant-tag">{entry.quant_label}</span>
                        )}

                        {runtime.isFree ? (
                          <span className="tag-badge cost-tag-free">$0.00 Fee</span>
                        ) : runtime.type === 'cloud' ? (
                          <span className="tag-badge cost-tag-paid">Cloud Tokens</span>
                        ) : null}

                        {runtime.type === 'local' && (
                          <>
                            <span
                              className="tag-badge param-tag"
                              title={`Context Window: ${entry.execution_params?.ctx_size || 8192} tokens in llama-server`}
                            >
                              {entry.execution_params?.ctx_size ? `${Math.round(entry.execution_params.ctx_size / 1024)}k ctx` : '8k ctx'}
                            </span>
                            <span
                              className="tag-badge param-tag"
                              title={`Max Output Budget: ${entry.execution_params?.max_output_tokens || 512} tokens per decision`}
                            >
                              {entry.execution_params?.max_output_tokens || 512} max out
                            </span>
                            <span
                              className="tag-badge param-tag"
                              title={`Temperature: ${entry.execution_params?.temperature ?? 0.0} (Greedy deterministic decoding)`}
                            >
                              t={entry.execution_params?.temperature ?? 0.0}
                            </span>
                            <span
                              className="tag-badge param-tag"
                              title={`Thinking Mode: ${entry.execution_params?.thinking_mode || 'off'} (${entry.execution_params?.thinking_mode === 'on' ? 'reasoning traces enabled' : 'direct JSON responses'})`}
                            >
                              think: {entry.execution_params?.thinking_mode || 'off'}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </td>

                  <td>
                    <div className="accuracy-bar-wrapper">
                      <div className="accuracy-bar-bg">
                        <div
                          className="accuracy-bar-fill"
                          style={{
                            width: `${Math.min(100, Math.max(0, entry.accuracy * 100))}%`,
                            backgroundColor: color,
                          }}
                        />
                      </div>
                      <span className="accuracy-pct-val">{entry.accuracy_pct}</span>
                    </div>
                    {entry.valid_accuracy_pct && entry.valid_count < entry.total_count && (
                      <div
                        style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '3px' }}
                        title={`Accuracy conditioned on valid responses only: ${entry.valid_accuracy_pct}`}
                      >
                        {entry.valid_accuracy_pct} valid-only
                      </div>
                    )}
                  </td>

                  <td>
                    <span className={`delta-badge ${deltaClass}`}>
                      {deltaStr}
                    </span>
                  </td>

                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {entry.latency_str}
                      </span>
                      <span
                        className={`speed-badge ${
                          entry.speed_class === 'baseline' ? 'baseline' : ''
                        }`}
                      >
                        {entry.speed_str}
                      </span>
                    </div>
                  </td>

                  <td>
                    <div style={{ fontSize: '12px' }}>
                      <strong style={{ color: 'var(--text)' }}>{entry.valid_rate_pct}</strong>
                      <span style={{ color: 'var(--text-muted)', marginLeft: '4px' }}>
                        ({entry.valid_count}/{entry.total_count})
                      </span>
                    </div>
                  </td>

                  <td>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      {entry.badges.map((b) => (
                        <span key={b.label} className={`kpi-badge ${b.class}`}>
                          {b.label}
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
