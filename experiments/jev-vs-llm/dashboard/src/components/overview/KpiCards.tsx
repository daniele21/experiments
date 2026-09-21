import React from 'react';
import type { KpiCardsData } from '../../types/benchmark';
import { Trophy, Zap, Scale, CheckCircle2 } from 'lucide-react';

interface KpiCardsProps {
  data: KpiCardsData;
}

export const KpiCards: React.FC<KpiCardsProps> = ({ data }) => {
  const { leader, fastest, sweet_spot, total_models, total_requests } = data;

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
              <span className="kpi-subtext">Rank #1</span>
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
              <span className="kpi-subtext">{fastest.speed_str}</span>
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
            <span className="kpi-subtext">Active</span>
          </div>
          <div className="kpi-model-name">Evaluated Systems</div>
          <div className="kpi-value-row">
            <span className="kpi-big-number">{total_models}</span>
            <span className="kpi-subtext">models tested</span>
          </div>
        </div>
        <div className="kpi-footer">
          <span>Total Requests: {total_requests}</span>
          <span>100% Local Inference</span>
        </div>
      </div>
    </div>
  );
};
