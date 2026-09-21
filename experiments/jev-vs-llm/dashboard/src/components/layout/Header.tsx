import React from 'react';
import type { BenchmarkMetadata } from '../../types/benchmark';
import { Layers, Calendar, MapPin, Tag } from 'lucide-react';

interface HeaderProps {
  metadata: BenchmarkMetadata;
}

export const Header: React.FC<HeaderProps> = ({ metadata }) => {
  return (
    <header className="top-header">
      <div>
        <div className="brand-kicker">
          <Layers size={13} />
          <span>Decision Benchmark Explorer</span>
        </div>
        <h1 className="header-title">Decision Model Benchmark</h1>
        <p className="header-subtitle">
          Comparing intent routing quality, execution latency, calibration and efficiency across local
          and cloud decision models. Filter models or switch tabs to explore deep case-level traces.
        </p>
      </div>
      <div className="header-meta">
        <div className="meta-pill">
          <Tag size={13} />
          <span>Run:</span>
          <code>{metadata.run_group}</code>
        </div>
        <div className="meta-pill">
          <Calendar size={13} />
          <span>Pricing Snapshot: {metadata.pricing_as_of}</span>
        </div>
        <div className="meta-pill">
          <MapPin size={13} />
          <span>Suite: {metadata.suite}</span>
        </div>
      </div>
    </header>
  );
};
