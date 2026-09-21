import React from 'react';
import type { LeaderboardEntry } from '../../types/benchmark';
import { ShieldCheck, Cpu, ArrowUpRight } from 'lucide-react';

interface LocalEfficiencyCardProps {
  entries: LeaderboardEntry[];
}

export const LocalEfficiencyCard: React.FC<LocalEfficiencyCardProps> = ({ entries }) => {
  if (entries.length < 2) return null;

  const topAcc = entries[0];
  const sweetSpot = entries.find((e) => e.badges.some((b) => b.label.includes('Sweet Spot'))) || entries[1];

  return (
    <div className="card" style={{ background: 'linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)' }}>
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--success)', background: 'var(--success-bg)', padding: '3px 8px', borderRadius: '9999px', marginBottom: '8px' }}>
            <ShieldCheck size={13} />
            <span>Local Inference Economics</span>
          </div>
          <h3 className="card-title">Zero API Fees &amp; Hardware Efficiency</h3>
          <p className="card-subtitle">
            Breaks down API cost by experiment workload and local inference advantages. Local quantized models run with zero provider API charges.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--surface-alt)', padding: '6px 12px', borderRadius: 'var(--radius-md)', fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>
          <Cpu size={15} />
          <span>Local Hardware</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginTop: '8px' }}>
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>
            Maximum Quality Peak
          </div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
            {topAcc.series}
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.45 }}>
            Delivers the highest intent accuracy at <strong>{topAcc.accuracy_pct}</strong> with median latency of <strong>{topAcc.latency_str}</strong>. Best suited for high-stakes routing where correctness outweighs latency.
          </p>
        </div>

        {sweetSpot && sweetSpot.series !== topAcc.series && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '16px' }}>
            <div style={{ fontSize: '12px', color: 'var(--success)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <ArrowUpRight size={14} />
              <span>Recommended Production Tradeoff</span>
            </div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text)', marginBottom: '4px' }}>
              {sweetSpot.series}
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.45 }}>
              Achieves <strong>{sweetSpot.accuracy_pct}</strong> ({sweetSpot.delta_str} vs top), while operating <strong>{sweetSpot.vs_leader_speed}</strong> ({sweetSpot.latency_str}). Delivers ~90% of maximum capability with minimal overhead.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
