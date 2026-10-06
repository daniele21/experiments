import {
  Layers,
  Sliders,
} from 'lucide-react';
import type { DashboardModel, DecisionModelSummary } from '../types';

export function ModelParamBadge({
  parameters_b,
  deployment,
}: {
  parameters_b?: number | null;
  deployment?: string;
}) {
  if (parameters_b != null) {
    return <span className="param-badge">{parameters_b}B</span>;
  }
  if (deployment === 'api') {
    return <span className="param-badge api-badge">API</span>;
  }
  return <span className="param-badge muted-badge">—</span>;
}

export function ModelQuantBadge({
  quantization,
  deployment,
}: {
  quantization?: string | null;
  deployment?: string;
}) {
  if (quantization) {
    return <span className="quant-badge">{quantization}</span>;
  }
  if (deployment === 'api') {
    return <span className="quant-badge api-quant">FP16</span>;
  }
  return <span className="quant-badge muted-badge">—</span>;
}

export function ModelTagList({ tags }: { tags?: string[] | null }) {
  if (!tags || tags.length === 0) return null;
  return (
    <div className="model-tag-list">
      {tags.map((tag) => (
        <span key={tag} className="model-tag-pill">
          {tag}
        </span>
      ))}
    </div>
  );
}

export function ModelSamplingMiniGrid({
  model,
}: {
  model: DashboardModel | DecisionModelSummary;
}) {
  const gen = model.generation_parameters;
  const temp = gen?.temperature != null ? gen.temperature : 0.0;
  const maxTokens = gen?.max_output_tokens ?? 256;
  const seed = gen?.seed ?? 42;
  const profile = model.execution_profile ?? 'core';

  return (
    <div className="model-sampling-box">
      <div className="sampling-box-title">
        <Sliders size={13} />
        <span>Sampling & Execution</span>
        <span className="profile-pill">{profile}</span>
      </div>
      <div className="sampling-grid">
        <div>
          <dt>Temp</dt>
          <dd>{temp}</dd>
        </div>
        <div>
          <dt>Max Tokens</dt>
          <dd>{maxTokens}</dd>
        </div>
        <div>
          <dt>Seed</dt>
          <dd>{seed}</dd>
        </div>
      </div>
    </div>
  );
}

export function ModelArchitectureCard({
  model,
}: {
  model: DashboardModel | DecisionModelSummary;
}) {
  const gen = model.generation_parameters;
  return (
    <div className="model-config-panel">
      <div className="model-config-columns">
        <div className="config-box">
          <h4>
            <Layers size={15} /> Architecture & Artifact
          </h4>
          <dl className="config-dl">
            <div>
              <dt>Family</dt>
              <dd><strong>{model.family ?? '—'}</strong></dd>
            </div>
            <div>
              <dt>Parameters</dt>
              <dd>
                <strong>
                  {model.parameters_b != null
                    ? `${model.parameters_b} Billion (${model.parameters_b}B)`
                    : model.deployment === 'api'
                      ? 'Closed API Model'
                      : '—'}
                </strong>
              </dd>
            </div>
            <div>
              <dt>Quantization</dt>
              <dd>
                <ModelQuantBadge
                  quantization={model.quantization}
                  deployment={model.deployment}
                />
              </dd>
            </div>
            <div>
              <dt>Artifact format</dt>
              <dd>{model.artifact_format ? model.artifact_format.toUpperCase() : (model.deployment === 'api' ? 'API Endpoint' : '—')}</dd>
            </div>
            <div>
              <dt>Effective Model ID</dt>
              <dd className="code-text">{model.effective_model_id || '—'}</dd>
            </div>
          </dl>
        </div>

        <div className="config-box">
          <h4>
            <Sliders size={15} /> Sampling & Runtime Configuration
          </h4>
          <dl className="config-dl">
            <div>
              <dt>Sampling temperature</dt>
              <dd><strong>{gen?.temperature != null ? gen.temperature : 0.0}</strong></dd>
            </div>
            <div>
              <dt>Max output tokens</dt>
              <dd><strong>{gen?.max_output_tokens ?? 256}</strong></dd>
            </div>
            <div>
              <dt>Random seed</dt>
              <dd><code>{gen?.seed ?? 42}</code></dd>
            </div>
            <div>
              <dt>Execution profile</dt>
              <dd><span className="profile-pill">{model.execution_profile ?? 'core'}</span></dd>
            </div>
            <div>
              <dt>Runtime key</dt>
              <dd className="code-text">{model.runtime_key || '—'}</dd>
            </div>
          </dl>
        </div>
      </div>

      {model.tags && model.tags.length > 0 ? (
        <div className="config-tags-footer">
          <span className="tags-label">Model tags:</span>
          <ModelTagList tags={model.tags} />
        </div>
      ) : null}
    </div>
  );
}

export function ModelParametersComparison({
  modelA,
  modelB,
}: {
  modelA: DashboardModel | DecisionModelSummary;
  modelB: DashboardModel | DecisionModelSummary;
}) {
  const genA = modelA.generation_parameters;
  const genB = modelB.generation_parameters;

  const rows = [
    {
      label: 'Family',
      valA: modelA.family ?? '—',
      valB: modelB.family ?? '—',
    },
    {
      label: 'Parameters count',
      valA: modelA.parameters_b != null ? `${modelA.parameters_b}B` : (modelA.deployment === 'api' ? 'Closed' : '—'),
      valB: modelB.parameters_b != null ? `${modelB.parameters_b}B` : (modelB.deployment === 'api' ? 'Closed' : '—'),
    },
    {
      label: 'Quantization',
      valA: modelA.quantization ?? (modelA.deployment === 'api' ? 'FP16' : '—'),
      valB: modelB.quantization ?? (modelB.deployment === 'api' ? 'FP16' : '—'),
    },
    {
      label: 'Format',
      valA: modelA.artifact_format?.toUpperCase() ?? (modelA.deployment === 'api' ? 'API' : '—'),
      valB: modelB.artifact_format?.toUpperCase() ?? (modelB.deployment === 'api' ? 'API' : '—'),
    },
    {
      label: 'Temperature',
      valA: genA?.temperature != null ? genA.temperature : 0.0,
      valB: genB?.temperature != null ? genB.temperature : 0.0,
    },
    {
      label: 'Max output tokens',
      valA: genA?.max_output_tokens ?? 256,
      valB: genB?.max_output_tokens ?? 256,
    },
    {
      label: 'Random seed',
      valA: genA?.seed ?? 42,
      valB: genB?.seed ?? 42,
    },
    {
      label: 'Execution profile',
      valA: modelA.execution_profile ?? 'core',
      valB: modelB.execution_profile ?? 'core',
    },
    {
      label: 'Runtime key',
      valA: modelA.runtime_key ?? '—',
      valB: modelB.runtime_key ?? '—',
    },
  ];

  return (
    <div className="param-comparison-table">
      <div className="param-comparison-header">
        <span>Parameter</span>
        <strong>{modelA.model_key}</strong>
        <strong>{modelB.model_key}</strong>
      </div>
      {rows.map((row) => {
        const isDiff = String(row.valA) !== String(row.valB);
        return (
          <div
            key={row.label}
            className={`param-comparison-row ${isDiff ? 'has-diff' : ''}`}
          >
            <span className="param-comp-label">{row.label}</span>
            <span className="param-comp-val">{String(row.valA)}</span>
            <span className="param-comp-val">{String(row.valB)}</span>
          </div>
        );
      })}
    </div>
  );
}
