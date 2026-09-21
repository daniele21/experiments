import React from 'react';
import type { KpiCardsData, HardwareInfo } from '../../types/benchmark';
import { Trophy, Zap, Scale, CheckCircle2, Cpu } from 'lucide-react';
import { getModelRuntime } from '../../config/theme';

interface KpiCardsProps {
  data: KpiCardsData;
  hardware?: HardwareInfo;
}

export const KpiCards: React.FC<KpiCardsProps> = ({ data, hardware }) => {
  const { leader, fastest, sweet_spot, total_models, total_requests } = data;

  const leaderRt = leader ? getModelRuntime(leader.provider, leader.series) : null;
  const fastestRt = fastest ? getModelRuntime(fastest.provider, fastest.series) : null;

  return (
    <div className="kpi-grid">
      {/* 1. Accuracy Leader */}
      {leader && (
        <div className="kpi-card kpi-gold">
          <div>
            <div className="kpi-label-row">
              <span className="kpi-badge badge-gold">
                <Trophy size={12} />
                <span>Accuracy Leader</span>
              </span>
              <span className="kpi-subtext">Rank #1 · {leaderRt?.shortLabel}</span>
            </div>
            <div className="kpi-model-name" title={leader.series}>
              {leader.series}
            </div>
            <div className="kpi-value-row">
              <span className="kpi-big-number">{leader.accuracy_pct}</span>
              <span className="kpi-subtext">Intent Accuracy</span>
            </div>
          </div>
          <div className="kpi-footer">
            <span>Latency: {leader.latency_str}</span>
            <span>{leader.valid_count}/{leader.total_count} valid</span>
          </div>
        </div>
      )}

      {/* 2. Speed Leader */}
      {fastest && (
        <div className="kpi-card kpi-blue">
          <div>
            <div className="kpi-label-row">
              <span className="kpi-badge badge-blue">
                <Zap size={12} />
                <span>Speed Champion</span>
              </span>
              <span className="kpi-subtext">{fastest.speed_str} · {fastestRt?.shortLabel}</span>
            </div>
            <div className="kpi-model-name" title={fastest.series}>
              {fastest.series}
            </div>
            <div className="kpi-value-row">
              <span className="kpi-big-number">{fastest.latency_str}</span>
              <span className="kpi-subtext">p50 Latency</span>
            </div>
          </div>
          <div className="kpi-footer">
            <span>Accuracy: {fastest.accuracy_pct}</span>
            <span>{fastest.vs_leader_speed}</span>
          </div>
        </div>
      )}

      {/* 3. Efficiency Sweet Spot */}
      {sweet_spot && (
        <div className="kpi-card kpi-emerald">
          <div>
            <div className="kpi-label-row">
              <span className="kpi-badge badge-emerald">
                <Scale size={12} />
                <span>Efficiency Pick</span>
              </span>
              <span className="kpi-subtext">{sweet_spot.vs_leader_speed}</span>
            </div>
            <div className="kpi-model-name" title={sweet_spot.series}>
              {sweet_spot.series}
            </div>
            <div className="kpi-value-row">
              <span className="kpi-big-number">{sweet_spot.accuracy_pct}</span>
              <span className="kpi-subtext">at {sweet_spot.latency_str}</span>
            </div>
          </div>
          <div className="kpi-footer">
            <span>Gap: {sweet_spot.delta_str}</span>
            <span>High Speed / Quality</span>
          </div>
        </div>
      )}

      {/* 4. Total Evaluated */}
      <div className="kpi-card kpi-slate">
        <div>
          <div className="kpi-label-row">
            <span className="kpi-badge badge-slate">
              <CheckCircle2 size={12} />
              <span>Benchmark Matrix</span>
            </span>
            <span className="kpi-subtext">
              {hardware?.chip ? `${hardware.chip}` : 'Active'}
            </span>
          </div>
          <div className="kpi-model-name">Evaluated Systems</div>
          <div className="kpi-value-row">
            <span className="kpi-big-number">{total_models}</span>
            <span className="kpi-subtext">models tested</span>
          </div>
        </div>
        <div className="kpi-footer">
          <span>Requests: {total_requests}</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <Cpu size={12} />
            <span>5 Local M3 Pro · 2 Cloud/Engine</span>
          </span>
        </div>
      </div>
    </div>
  );
};
