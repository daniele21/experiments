import { Check, ChevronDown, Filter, Search, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { DecisionModelSummary } from '../types';
import { modelShortLabel, modelVisual } from '../modelVisuals';

export type DeploymentFilter = 'all' | 'local' | 'api';

export function ModelMarker({
  signature,
  size = 9,
}: {
  signature: string;
  size?: number;
}) {
  const visual = modelVisual(signature);
  return (
    <span
      className={'model-marker marker-' + visual.marker}
      style={{
        '--model-color': visual.color,
        '--marker-size': size + 'px',
      } as React.CSSProperties}
      aria-hidden="true"
    />
  );
}

export function ModelLegend({
  models,
  hoveredModel,
  selectedModel,
  onHover,
  onSelect,
  compact = false,
}: {
  models: DecisionModelSummary[];
  hoveredModel?: string | null;
  selectedModel?: string | null;
  onHover?: (signature: string | null) => void;
  onSelect?: (signature: string) => void;
  compact?: boolean;
}) {
  return (
    <div className={compact ? 'model-legend compact' : 'model-legend'}>
      {models.map((model) => {
        const dimmed = hoveredModel && hoveredModel !== model.model_signature;
        return (
          <button
            type="button"
            key={model.model_signature}
            className={
              'model-legend-item ' +
              (selectedModel === model.model_signature ? 'selected ' : '') +
              (dimmed ? 'dimmed' : '')
            }
            onMouseEnter={() => onHover?.(model.model_signature)}
            onMouseLeave={() => onHover?.(null)}
            onFocus={() => onHover?.(model.model_signature)}
            onBlur={() => onHover?.(null)}
            onClick={() => onSelect?.(model.model_signature)}
            title={model.model_key}
          >
            <ModelMarker signature={model.model_signature} />
            <span>{modelShortLabel(model.model_key)}</span>
          </button>
        );
      })}
    </div>
  );
}

export function ModelFilterBar({
  models,
  visibleSignatures,
  deployment,
  onVisibleSignaturesChange,
  onDeploymentChange,
  hoveredModel,
  selectedModel,
  onHover,
  onSelect,
}: {
  models: DecisionModelSummary[];
  visibleSignatures: string[];
  deployment: DeploymentFilter;
  onVisibleSignaturesChange: (signatures: string[]) => void;
  onDeploymentChange: (deployment: DeploymentFilter) => void;
  hoveredModel?: string | null;
  selectedModel?: string | null;
  onHover?: (signature: string | null) => void;
  onSelect?: (signature: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const deploymentModels = useMemo(
    () =>
      models.filter(
        (model) => deployment === 'all' || model.deployment === deployment,
      ),
    [models, deployment],
  );
  const filteredModels = useMemo(() => {
    const query = search.trim().toLowerCase();
    return deploymentModels.filter(
      (model) =>
        !query ||
        model.model_key.toLowerCase().includes(query) ||
        model.model_id.toLowerCase().includes(query) ||
        model.provider_key.toLowerCase().includes(query),
    );
  }, [deploymentModels, search]);

  const active = new Set(visibleSignatures);
  const effectiveVisible =
    visibleSignatures.length > 0
      ? deploymentModels.filter((model) => active.has(model.model_signature))
      : deploymentModels;

  const setPreset = (
    preset: 'all' | 'top-quality' | 'top-local' | 'lowest-cost',
  ) => {
    if (preset === 'all') {
      onVisibleSignaturesChange([]);
      return;
    }
    let candidates = [...deploymentModels];
    if (preset === 'top-local') {
      candidates = candidates.filter((model) => model.deployment === 'local');
    }
    if (preset === 'lowest-cost') {
      candidates = candidates
        .filter(
          (model) =>
            model.provider_cost_known &&
            model.provider_cost_per_1k_cases_usd != null,
        )
        .sort(
          (a, b) =>
            Number(a.provider_cost_per_1k_cases_usd) -
            Number(b.provider_cost_per_1k_cases_usd),
        );
    } else {
      candidates.sort(
        (a, b) =>
          Number(b.overall_quality_score ?? -1) -
          Number(a.overall_quality_score ?? -1),
      );
    }
    onVisibleSignaturesChange(
      candidates.slice(0, Math.min(5, candidates.length)).map((m) => m.model_signature),
    );
  };

  const toggleModel = (signature: string) => {
    const current =
      visibleSignatures.length > 0
        ? new Set(visibleSignatures)
        : new Set(deploymentModels.map((model) => model.model_signature));
    if (current.has(signature)) current.delete(signature);
    else current.add(signature);

    const next = deploymentModels
      .filter((model) => current.has(model.model_signature))
      .map((model) => model.model_signature);
    onVisibleSignaturesChange(
      next.length === deploymentModels.length ? [] : next,
    );
  };

  return (
    <section className="model-filter-bar">
      <div className="model-filter-main">
        <div className="segmented model-deployment-filter">
          {(['all', 'local', 'api'] as const).map((value) => (
            <button
              type="button"
              key={value}
              className={deployment === value ? 'active' : ''}
              onClick={() => onDeploymentChange(value)}
            >
              {value === 'all' ? 'All' : value === 'local' ? 'Local' : 'API'}
            </button>
          ))}
        </div>

        <button
          type="button"
          className={open ? 'model-filter-trigger active' : 'model-filter-trigger'}
          onClick={() => setOpen((value) => !value)}
        >
          <Filter size={14} />
          Models
          <strong>{effectiveVisible.length}/{deploymentModels.length}</strong>
          <ChevronDown size={14} />
        </button>

        <div className="model-filter-presets">
          <button type="button" onClick={() => setPreset('all')}>All models</button>
          <button type="button" onClick={() => setPreset('top-quality')}>Top 5 quality</button>
          <button type="button" onClick={() => setPreset('top-local')}>Top local</button>
          <button type="button" onClick={() => setPreset('lowest-cost')}>Lowest cost</button>
        </div>

        {visibleSignatures.length ? (
          <button
            type="button"
            className="clear-model-filter"
            onClick={() => onVisibleSignaturesChange([])}
          >
            <X size={12} /> Clear
          </button>
        ) : null}
      </div>

      {open ? (
        <div className="model-picker-popover">
          <label className="model-search">
            <Search size={14} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search model, provider or ID"
              autoFocus
            />
          </label>
          <div className="model-picker-list">
            {filteredModels.map((model) => {
              const checked =
                visibleSignatures.length === 0 ||
                visibleSignatures.includes(model.model_signature);
              return (
                <button
                  type="button"
                  key={model.model_signature}
                  className="model-picker-row"
                  onClick={() => toggleModel(model.model_signature)}
                  onMouseEnter={() => onHover?.(model.model_signature)}
                  onMouseLeave={() => onHover?.(null)}
                >
                  <span className={checked ? 'model-checkbox checked' : 'model-checkbox'}>
                    {checked ? <Check size={11} /> : null}
                  </span>
                  <ModelMarker signature={model.model_signature} size={10} />
                  <span className="model-picker-name">
                    <strong>{model.model_key}</strong>
                    <small>{model.deployment} · {model.provider_key}</small>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      <ModelLegend
        models={effectiveVisible}
        hoveredModel={hoveredModel}
        selectedModel={selectedModel}
        onHover={onHover}
        onSelect={onSelect}
        compact={effectiveVisible.length > 8}
      />
    </section>
  );
}
