import React from 'react';
import type { LeaderboardEntry } from '../../types/benchmark';
import { getSeriesColor } from '../../config/theme';

interface LeaderboardProps {
  entries: LeaderboardEntry[];
  selectedSeries: Set<string>;
}

export const Leaderboard: React.FC<LeaderboardProps> = ({ entries, selectedSeries }) => {
  const visibleEntries = entries.filter((e) => selectedSeries.has(e.series));

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">Model Performance Leaderboard</h2>
        <p className="card-subtitle">
          Direct side-by-side gap analysis ranked by intent classification correctness. Delta shows the
          accuracy difference relative to the top-performing model.
        </p>
      </div>

      <div className="leaderboard-container">
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '80px' }}>Rank</th>
              <th>Model</th>
              <th style={{ minWidth: '220px' }}>Accuracy</th>
              <th style={{ width: '130px' }}>Gap vs Top</th>
              <th style={{ minWidth: '160px' }}>p50 Latency</th>
              <th style={{ width: '120px' }}>Validity</th>
              <th>Highlights</th>
            </tr>
          </thead>
          <tbody>
            {visibleEntries.map((entry, idx) => {
              const color = getSeriesColor(entry.series, idx);
              return (
                <tr key={entry.series}>
                  <td>
                    <div className="rank-cell">
                      <span className="medal-icon">{entry.medal}</span>
                      <span>#{entry.rank}</span>
                    </div>
                  </td>

                  <td>
                    <div className="model-cell">
                      <span className="model-name-text">{entry.series}</span>
                      <div className="model-tags">
                        {entry.quant_label && (
                          <span className="tag-badge quant-tag">{entry.quant_label}</span>
                        )}
                        <span className="tag-badge">{entry.provider}</span>
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
                  </td>

                  <td>
                    <span className={`delta-badge ${entry.delta_class}`}>
                      {entry.delta_str}
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
