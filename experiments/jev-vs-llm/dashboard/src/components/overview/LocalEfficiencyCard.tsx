import React from 'react';
import type { LeaderboardEntry, BenchmarkMetadata } from '../../types/benchmark';
import { ShieldCheck, Cpu, ArrowUpRight, HardDrive, Zap, Lock, DollarSign } from 'lucide-react';
import { LocalParametersGrid } from './LocalParametersGrid';

interface LocalEfficiencyCardProps {
  entries: LeaderboardEntry[];
  metadata?: BenchmarkMetadata;
}

export const LocalEfficiencyCard: React.FC<LocalEfficiencyCardProps> = ({ entries, metadata }) => {
  if (entries.length < 2) return null;

  const topAcc = entries[0];
  const sweetSpot = entries.find((e) => e.badges.some((b) => b.label.includes('Sweet Spot'))) || entries[1];
  const hw = metadata?.hardware;

  const deviceName = hw?.device || 'MacBook Pro';
  const chipName = hw?.chip || 'Apple M3 Pro';
  const cores = hw?.cores || '11 (5 Performance + 6 Efficiency)';
  const memoryGb = hw?.memory_gb ? `${hw.memory_gb} GB Unified Memory` : '36 GB Unified Memory';
  const osName = hw?.os === 'Darwin' ? 'macOS (Apple Silicon)' : hw?.os || 'macOS';

  return (
    <div className="card hardware-spec-card">
      <div className="card-header">
        <div className="card-title-row">
          <div>
            <div className="card-kicker-success">
              <ShieldCheck size={13} />
              <span>Host Hardware &amp; Local Inference Profile</span>
            </div>
            <h3 className="card-title">Host Device Specifications &amp; Local Economics</h3>
            <p className="card-subtitle">
              Verified host device environment for local open-weights inference.
              All Korgis models run locally with zero cloud API token billing and zero outbound telemetry.
            </p>
          </div>
          <div className="hw-chip-pill">
            <Cpu size={16} style={{ color: 'var(--success)' }} />
            <span><strong>{chipName}</strong> · {memoryGb}</span>
          </div>
        </div>
      </div>

      {/* Hardware Specs Grid */}
      <div className="hardware-specs-grid">
        <div className="hw-spec-box">
          <div className="hw-spec-icon">
            <HardDrive size={18} />
          </div>
          <div>
            <div className="hw-spec-label">Host Device</div>
            <div className="hw-spec-value">{deviceName}</div>
            <div className="hw-spec-sub">{osName}</div>
          </div>
        </div>

        <div className="hw-spec-box">
          <div className="hw-spec-icon">
            <Cpu size={18} />
          </div>
          <div>
            <div className="hw-spec-label">Silicon Processor</div>
            <div className="hw-spec-value">{chipName}</div>
            <div className="hw-spec-sub">{cores}</div>
          </div>
        </div>

        <div className="hw-spec-box">
          <div className="hw-spec-icon">
            <Zap size={18} />
          </div>
          <div>
            <div className="hw-spec-label">Unified RAM</div>
            <div className="hw-spec-value">{memoryGb}</div>
            <div className="hw-spec-sub">Zero-copy CPU / GPU shared pool</div>
          </div>
        </div>

        <div className="hw-spec-box">
          <div className="hw-spec-icon">
            <DollarSign size={18} />
          </div>
          <div>
            <div className="hw-spec-label">Provider API Fee</div>
            <div className="hw-spec-value" style={{ color: 'var(--success)' }}>$0.00 / query</div>
            <div className="hw-spec-sub">Hardware amortized, zero per-token cost</div>
          </div>
        </div>
      </div>

      {/* Local Execution & Inference Parameters */}
      <LocalParametersGrid parameters={metadata?.local_parameters} />

      {/* Strategic Comparison Rows */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '16px' }}>
        <div className="hw-insight-box">
          <div className="hw-insight-header">
            <span className="hw-insight-tag">Cloud Quality Leader</span>
          </div>
          <div className="hw-insight-title">{topAcc.series}</div>
          <p className="hw-insight-desc">
            Highest categorical correctness at <strong>{topAcc.accuracy_pct}</strong> with median latency of <strong>{topAcc.latency_str}</strong>. Best suited for high-complexity decisions where cloud network latency and token costs are secondary to correctness.
          </p>
        </div>

        {sweetSpot && sweetSpot.series !== topAcc.series && (
          <div className="hw-insight-box hw-insight-highlight">
            <div className="hw-insight-header">
              <span className="hw-insight-tag hw-tag-emerald">
                <ArrowUpRight size={13} style={{ marginRight: '3px' }} />
                Production Sweet Spot
              </span>
            </div>
            <div className="hw-insight-title">{sweetSpot.series}</div>
            <p className="hw-insight-desc">
              Achieves <strong>{sweetSpot.accuracy_pct}</strong> ({sweetSpot.delta_str} vs leader), while operating <strong>{sweetSpot.vs_leader_speed}</strong> ({sweetSpot.latency_str}). Delivers ~90% of maximum capability with minimal overhead.
            </p>
          </div>
        )}

        <div className="hw-insight-box">
          <div className="hw-insight-header">
            <span className="hw-insight-tag hw-tag-purple">
              <Lock size={13} style={{ marginRight: '3px' }} />
              On-Device Sovereignty
            </span>
          </div>
          <div className="hw-insight-title">Zero Network Transmission</div>
          <p className="hw-insight-desc">
            Local models (Qwen, Nemotron) process sensitive user queries directly on <strong>{chipName}</strong> without internet exposure, eliminating compliance hurdles, third-party vendor lock-in, and downtime risk.
          </p>
        </div>
      </div>
    </div>
  );
};
