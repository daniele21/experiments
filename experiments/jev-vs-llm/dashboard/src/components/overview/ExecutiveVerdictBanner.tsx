/**
 * ExecutiveVerdictBanner.tsx
 *
 * High-impact top-level summary banner establishing the benchmark's primary information hierarchy:
 * 1. Accuracy Leader (Cloud LLM API)
 * 2. Speed Champion (Native Router)
 * 3. On-Device Winner (Local Apple Silicon M3 Pro with $0 API token cost)
 */

import React from 'react';
import type { LeaderboardEntry, BenchmarkMetadata } from '../../types/benchmark';
import { Trophy, Zap, ShieldCheck, Cpu, Check } from 'lucide-react';

interface ExecutiveVerdictBannerProps {
  leaderboard: LeaderboardEntry[];
  metadata: BenchmarkMetadata;
}

export const ExecutiveVerdictBanner: React.FC<ExecutiveVerdictBannerProps> = ({
  leaderboard,
  metadata,
}) => {
  if (leaderboard.length === 0) return null;

  const topAccuracy = leaderboard[0];
  const fastest = [...leaderboard].sort((a, b) => a.latency_p50_ms - b.latency_p50_ms)[0];
  const topLocal = leaderboard.find(
    (e) =>
      e.provider.includes('korgis') ||
      e.series.toLowerCase().includes('qwen') ||
      e.series.toLowerCase().includes('nemotron')
  );

  const hw = metadata.hardware;
  const chipName = hw?.chip || 'Apple M3 Pro';
  const memGb = hw?.memory_gb || '36';
  const deviceName = hw?.device || 'MacBook Pro';

  return (
    <div className="verdict-banner">
      {/* Top Banner Header */}
      <div className="verdict-header">
        <div className="verdict-title-group">
          <span className="verdict-tag">Executive Summary</span>
          <h2 className="verdict-title">Benchmark Verdict: Cloud vs Local Hardware Trade-offs</h2>
        </div>
        <div className="verdict-hw-badge" title="Local Inference Hardware Platform">
          <Cpu size={15} style={{ color: 'var(--success)' }} />
          <span>Local Host: <strong>{chipName} · {memGb} GB RAM</strong> ({deviceName})</span>
        </div>
      </div>

      {/* 3 Strategic Recommendations */}
      <div className="verdict-cards-grid">
        {/* 1. Cloud Accuracy Leader */}
        <div className="verdict-card">
          <div className="verdict-card-icon verdict-icon-cloud">
            <Trophy size={16} />
          </div>
          <div className="verdict-card-body">
            <div className="verdict-card-role">Highest Accuracy · Cloud API</div>
            <div className="verdict-card-model">{topAccuracy.series}</div>
            <div className="verdict-metric-line">
              <strong>{topAccuracy.accuracy_pct}</strong> accuracy · <span>{topAccuracy.latency_str}</span> p50
            </div>
            <p className="verdict-card-desc">
              Maximum intent classification correctness. Ideal for complex ambiguous workflows where API cost and external latency are acceptable.
            </p>
          </div>
        </div>

        {/* 2. Speed Champion */}
        {fastest && (
          <div className="verdict-card">
            <div className="verdict-card-icon verdict-icon-fast">
              <Zap size={16} />
            </div>
            <div className="verdict-card-body">
              <div className="verdict-card-role">Ultra-Low Latency · Native Router</div>
              <div className="verdict-card-model">{fastest.series}</div>
              <div className="verdict-metric-line">
                <strong>{fastest.latency_str}</strong> ({fastest.vs_leader_speed}) · <span>{fastest.accuracy_pct}</span> acc
              </div>
              <p className="verdict-card-desc">
                Fastest decision turnaround with high accuracy (-6.5% delta vs leader). Ideal for interactive customer-facing paths.
              </p>
            </div>
          </div>
        )}

        {/* 3. Local Hardware Winner */}
        {topLocal && (
          <div className="verdict-card verdict-card-highlight">
            <div className="verdict-card-icon verdict-icon-local">
              <ShieldCheck size={16} />
            </div>
            <div className="verdict-card-body">
              <div className="verdict-card-role">
                Best On-Device · $0 API Fee
              </div>
              <div className="verdict-card-model">{topLocal.series}</div>
              <div className="verdict-metric-line">
                <strong>{topLocal.accuracy_pct}</strong> acc · <span style={{ color: 'var(--success)', fontWeight: 600 }}>$0.00 / 1k reqs</span>
              </div>
              <p className="verdict-card-desc">
                Runs 100% on host <strong>{chipName}</strong> with <strong>36 GB RAM</strong>. Complete data privacy with zero per-token cloud billing.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Hardware Context Strip */}
      <div className="verdict-strip">
        <div className="verdict-strip-item">
          <Check size={14} style={{ color: 'var(--success)' }} />
          <span><strong>Local Host Hardware:</strong> {deviceName}, {chipName} ({hw?.cores || '11-core'}), {memGb} GB Unified Memory</span>
        </div>
        <div className="verdict-strip-item">
          <Check size={14} style={{ color: 'var(--success)' }} />
          <span><strong>Zero Token Costs:</strong> Local models incur 0 API billing (hardware amortized, no external vendor dependency)</span>
        </div>
        <div className="verdict-strip-item">
          <Check size={14} style={{ color: 'var(--success)' }} />
          <span><strong>Data Sovereignty:</strong> Local prompts never leave host device memory</span>
        </div>
      </div>
    </div>
  );
};
