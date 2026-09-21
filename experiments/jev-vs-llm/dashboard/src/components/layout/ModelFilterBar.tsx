import React from 'react';
import type { ModelSpec } from '../../types/benchmark';
import { getSeriesColor } from '../../config/theme';

interface ModelFilterBarProps {
  models: ModelSpec[];
  selectedSeries: Set<string>;
  onToggleSeries: (series: string) => void;
}

export const ModelFilterBar: React.FC<ModelFilterBarProps> = ({
  models,
  selectedSeries,
  onToggleSeries,
}) => {
  return (
    <div className="model-filter-bar">
      <span className="filter-label">Filter:</span>
      {models.map((model, idx) => {
        const isSelected = selectedSeries.has(model.series);
        const color = getSeriesColor(model.series, idx);
        return (
          <button
            key={model.series}
            className={`model-chip ${isSelected ? 'active' : 'inactive'}`}
            onClick={() => onToggleSeries(model.series)}
            title={isSelected ? 'Click to hide from charts' : 'Click to show in charts'}
          >
            <span
              className="chip-color-dot"
              style={{ backgroundColor: color }}
            />
            <span>{model.series}</span>
          </button>
        );
      })}
    </div>
  );
};
