import React from 'react';
import type { BenchmarkMetadata } from '../../types/benchmark';
import { Layers, Calendar, MapPin, Tag, Cpu } from 'lucide-react';

interface HeaderProps {
  metadata: BenchmarkMetadata;
}

export const Header: React.FC<HeaderProps> = ({ metadata }) => {
  const hw = metadata.hardware;
  const hwString = hw?.chip
    ? `${hw.chip} · ${hw.memory_gb ? `${hw.memory_gb}GB RAM` : ''} (${hw.device || 'Host'})`
    : null;

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
          and cloud decision models. Latest run per model configuration and dataset.
        </p>
      </div>
      <div className="header-meta">
        {hwString && (
          <div className="meta-pill meta-pill-hardware" title={`Local Host: ${hw?.device || ''} with ${hw?.chip || ''}, ${hw?.cores || ''} cores, ${hw?.memory_gb || ''}GB RAM`}>
            <Cpu size={13} style={{ color: 'var(--success)' }} />
            <span>Local Device: <strong style={{ color: 'var(--text)' }}>{hwString}</strong></span>
          </div>
        )}
        <div className="meta-pill">
          <Tag size={13} />
          <span>Latest runs only</span>
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
