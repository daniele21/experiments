import React from 'react';
import type { ModelSpec } from '../../types/benchmark';
import { getSeriesColor, getModelRuntime } from '../../config/theme';
import { Cpu, Cloud, Zap } from 'lucide-react';

interface ModelFilterBarProps {
  models: ModelSpec[];
  selectedSeries: Set<string>;
  onToggleSeries: (series: string) => void;
  onSetPreset?: (preset: 'all' | 'local' | 'non-local') => void;
}

export const ModelFilterBar: React.FC<ModelFilterBarProps> = ({
  models,
  selectedSeries,
  onToggleSeries,
  onSetPreset,
}) => {
  const localCount = models.filter((m) => getModelRuntime(m.provider, m.series).type === 'local').length;
  const isAllSelected = selectedSeries.size === models.length;
  const isLocalOnly =
    selectedSeries.size === localCount &&
    Array.from(selectedSeries).every((s) => {
      const m = models.find((mod) => mod.series === s);
      return m ? getModelRuntime(m.provider, m.series).type === 'local' : false;
    });

  return (
    <div className="model-filter-bar">
      <div className="filter-presets">
        <span className="filter-label">Filter:</span>
        {onSetPreset && (
          <div className="preset-btn-group">
            <button
              className={`preset-btn ${isAllSelected ? 'active' : ''}`}
              onClick={() => onSetPreset('all')}
              title="Show all evaluated models"
            >
              All ({models.length})
            </button>
            <button
              className={`preset-btn ${isLocalOnly ? 'active' : ''}`}
              onClick={() => onSetPreset('local')}
              title="Show only local models running on Apple Silicon"
            >
              <Cpu size={12} style={{ color: 'var(--success)' }} />
              <span>Apple M3 Pro ({localCount})</span>
            </button>
          </div>
        )}
      </div>

      <div className="filter-chips-row">
        {models.map((model, idx) => {
          const isSelected = selectedSeries.has(model.series);
          const color = getSeriesColor(model.series, idx);
          const runtime = getModelRuntime(model.provider, model.series);

          const chipKey = model.series_id || `${model.series}_${model.dataset || 'ds'}_${idx}`;
          return (
            <button
              key={chipKey}
              className={`model-chip ${isSelected ? 'active' : 'inactive'}`}
              onClick={() => onToggleSeries(model.series)}
              title={`${model.series} · ${model.dataset_label || (model.dataset === 'public' ? 'Banking77 (77)' : 'Smoke (24)')} · ${runtime.label} (${isSelected ? 'Click to hide' : 'Click to show'})`}
            >
              <span
                className="chip-color-dot"
                style={{ backgroundColor: color }}
              />
              <span className="chip-series-text">{model.series}</span>
              {model.dataset && (
                <span className={`chip-ds-badge chip-ds-${model.dataset}`}>
                  {model.dataset === 'public' ? '77' : '24'}
                </span>
              )}
              {model.thinking_mode === 'on' && (
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    padding: '1px 5px',
                    borderRadius: '4px',
                    background: 'rgba(168, 85, 247, 0.15)',
                    color: '#a855f7',
                    border: '1px solid rgba(168, 85, 247, 0.35)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '2px',
                  }}
                  title="Reasoning / Thinking traces active"
                >
                  🧠 Think
                </span>
              )}
              <span
                className="chip-rt-badge"
                style={{
                  backgroundColor: runtime.badgeBg,
                  color: runtime.badgeColor,
                  border: `1px solid ${runtime.badgeBorder}`,
                }}
              >
                {runtime.type === 'local' ? (
                  <Cpu size={10} style={{ marginRight: '2px' }} />
                ) : runtime.type === 'cloud' ? (
                  <Cloud size={10} style={{ marginRight: '2px' }} />
                ) : (
                  <Zap size={10} style={{ marginRight: '2px' }} />
                )}
                {runtime.shortLabel}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
