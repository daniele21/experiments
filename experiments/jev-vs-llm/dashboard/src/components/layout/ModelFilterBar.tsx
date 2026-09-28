import React, { useState } from 'react';
import type { ModelSpec } from '../../types/benchmark';
import {
  getModelRuntime,
  formatCompactModelName,
  FILTER_BAR_CONFIG,
  BAR_GRADIENT_CONFIG,
} from '../../config/theme';
import { Cpu, Cloud, ChevronDown, ChevronUp, RotateCcw } from 'lucide-react';

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
  const [isExpanded, setIsExpanded] = useState<boolean>(FILTER_BAR_CONFIG.defaultExpanded);

  const localCount = models.filter(
    (m) => getModelRuntime(m.provider, m.series).type === 'local'
  ).length;

  const nonLocalCount = models.filter(
    (m) => getModelRuntime(m.provider, m.series).type !== 'local'
  ).length;

  const isAllSelected = selectedSeries.size === models.length;

  const isLocalOnly =
    selectedSeries.size === localCount &&
    Array.from(selectedSeries).every((s) => {
      const m = models.find((mod) => mod.series === s);
      return m ? getModelRuntime(m.provider, m.series).type === 'local' : false;
    });

  const isNonLocalOnly =
    selectedSeries.size === nonLocalCount &&
    Array.from(selectedSeries).every((s) => {
      const m = models.find((mod) => mod.series === s);
      return m ? getModelRuntime(m.provider, m.series).type !== 'local' : false;
    });

  return (
    <div className="model-filter-bar">
      {/* 1. Header with quick presets & compact controls */}
      <div className="filter-bar-header">
        <div className="filter-presets">
          <span className="filter-label">Models:</span>
          {onSetPreset && (
            <div className="preset-btn-group">
              <button
                type="button"
                className={`preset-btn ${isAllSelected ? 'active' : ''}`}
                onClick={() => onSetPreset('all')}
                title="Show all evaluated models"
              >
                All ({models.length})
              </button>
              <button
                type="button"
                className={`preset-btn ${isLocalOnly ? 'active' : ''}`}
                onClick={() => onSetPreset('local')}
                title="Show only local models running on Apple Silicon"
              >
                <Cpu size={11} style={{ color: 'var(--success)' }} />
                <span>Apple M3 Pro ({localCount})</span>
              </button>
              {nonLocalCount > 0 && (
                <button
                  type="button"
                  className={`preset-btn ${isNonLocalOnly ? 'active' : ''}`}
                  onClick={() => onSetPreset('non-local')}
                  title="Show only Cloud and Native reference models"
                >
                  <Cloud size={11} style={{ color: 'var(--accent)' }} />
                  <span>Cloud / Native ({nonLocalCount})</span>
                </button>
              )}
            </div>
          )}
        </div>

        <div className="filter-actions">
          <span className="filter-count-badge">
            {selectedSeries.size}/{models.length} active
          </span>

          {!isAllSelected && onSetPreset && (
            <button
              type="button"
              className="filter-action-btn"
              onClick={() => onSetPreset('all')}
              title="Reset filter to show all models"
            >
              <RotateCcw size={10} />
              <span>Reset</span>
            </button>
          )}

          <button
            type="button"
            className="filter-toggle-btn"
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? 'Hide individual model chips' : 'Customize individual model filters'}
          >
            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            <span>{isExpanded ? 'Hide chips' : 'Filter by model'}</span>
          </button>
        </div>
      </div>

      {/* 2. Compact, Streamlined Model Chips (visible when expanded) */}
      {isExpanded && (
        <div className="filter-chips-row">
          {models.map((model, idx) => {
            const isSelected = selectedSeries.has(model.series);
            const runtime = getModelRuntime(model.provider, model.series);
            const chipKey = model.series_id || `${model.series}_${model.dataset || 'ds'}_${idx}`;
            const label = FILTER_BAR_CONFIG.compactLabels
              ? formatCompactModelName(model.series)
              : model.series;

            const tooltip = `${model.series}
Hardware: ${runtime.hardwareSummary}
Runtime: ${runtime.label}
Dataset: ${model.dataset_label || (model.dataset === 'public' ? 'Banking77 (77 items)' : 'Smoke (24 items)')}
Status: ${isSelected ? 'Active (click to hide)' : 'Hidden (click to show)'}`;

            return (
              <button
                key={chipKey}
                type="button"
                className={`model-chip ${isSelected ? 'active' : 'inactive'}`}
                onClick={() => onToggleSeries(model.series)}
                title={tooltip}
              >
                <span
                  className="chip-color-dot"
                  style={{ background: isSelected ? BAR_GRADIENT_CONFIG.getCssGradient() : 'var(--text-light)' }}
                />
                <span className="chip-series-text">{label}</span>
                {FILTER_BAR_CONFIG.showThinkingIcon && model.thinking_mode === 'on' && (
                  <span className="chip-mini-icon" title="Thinking mode enabled">
                    🧠
                  </span>
                )}
                {FILTER_BAR_CONFIG.showCloudIcon && runtime.type === 'cloud' && (
                  <span className="chip-mini-icon" title="Cloud API">
                    <Cloud size={10} style={{ color: 'var(--accent)' }} />
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
