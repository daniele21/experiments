import { ChevronRight, Info, Sparkles, Trophy } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { AppLink } from './Shell';
import type {
  DecisionDatasetSummary,
  DecisionModelSummary,
} from '../types';
import { milliseconds, score, usd } from '../utils';

export function DeploymentBadge({ deployment }: { deployment: string }) {
  const normalized = deployment.toLowerCase();
  return (
    <span className={'deployment-badge ' + normalized}>
      {normalized === 'local' ? 'Local' : normalized === 'api' ? 'API' : deployment}
    </span>
  );
}

export function MetricCard({
  icon,
  label,
  model,
  value,
  caption,
  tone = 'blue',
  onClick,
}: {
  icon: ReactNode;
  label: string;
  model: string;
  value: string;
  caption: string;
  tone?: 'blue' | 'green' | 'amber' | 'violet';
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      className={'metric-card tone-' + tone}
      onClick={onClick}
    >
      <div className="metric-card-top">
        <span className="metric-icon">{icon}</span>
        <span className="metric-label">{label}</span>
      </div>
      <strong className="metric-model">{model}</strong>
      <div className="metric-value">{value}</div>
      <span className="metric-caption">{caption}</span>
      <span className="metric-spark" aria-hidden="true">
        <i /><i /><i /><i /><i /><i />
      </span>
    </button>
  );
}

function shortModelLabel(value: string): string {
  return value
    .replace(/-q\d.*$/i, '')
    .replace(/-nano-/i, ' ')
    .replace(/-v-?\d+(?:\.\d+)*-/i, ' ')
    .replace(/-luna$/i, '')
    .replaceAll('-', ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 18);
}

function scaleLog(value: number, min: number, max: number): number {
  if (value <= 0) return 0;
  const lo = Math.log10(Math.max(min, Number.MIN_VALUE));
  const hi = Math.log10(Math.max(max, min * 1.001));
  const point = Math.log10(value);
  return (point - lo) / (hi - lo || 1);
}

export function TradeoffScatter({
  title,
  description,
  models,
  xMetric,
  selectedModel,
  onSelect,
}: {
  title: string;
  description: string;
  models: DecisionModelSummary[];
  xMetric: 'latency' | 'cost';
  selectedModel?: string | null;
  onSelect?: (modelSignature: string) => void;
}) {
  const eligible = models.filter((model) => {
    const x =
      xMetric === 'latency'
        ? model.latency_p50_ms
        : model.provider_cost_per_1k_cases_usd;
    return x != null && x > 0 && model.overall_quality_score != null;
  });
  const xs = eligible.map((model) =>
    xMetric === 'latency'
      ? Number(model.latency_p50_ms)
      : Number(model.provider_cost_per_1k_cases_usd),
  );
  const minX = xs.length ? Math.min(...xs) / 1.7 : 0.01;
  const maxX = xs.length ? Math.max(...xs) * 1.7 : 1000;
  const plotted = eligible.map((model) => {
    const xValue =
      xMetric === 'latency'
        ? Number(model.latency_p50_ms)
        : Number(model.provider_cost_per_1k_cases_usd);
    const x =
      48 +
      Math.max(0, Math.min(1, scaleLog(xValue, minX, maxX))) * 354;
    const quality = Number(model.overall_quality_score);
    const y =
      210 - Math.max(0, Math.min(1, (quality - 40) / 60)) * 170;
    const frontier =
      xMetric === 'latency'
        ? model.observed_quality_latency_pareto
        : model.known_provider_cost_quality_pareto;
    return { model, xValue, x, quality, y, frontier };
  });
  const frontierPoints = plotted
    .filter((point) => point.frontier)
    .sort((a, b) => a.x - b.x);

  return (
    <section className="analysis-card scatter-card">
      <div className="section-heading compact">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <span className="info-dot" title="Dashed frontier marks non-dominated observed points.">
          <Info size={14} />
        </span>
      </div>
      {eligible.length ? (
        <div className="scatter-wrap">
          <svg
            className="scatter-svg"
            viewBox="0 0 420 250"
            role="img"
            aria-label={title}
          >
            <g className="scatter-grid">
              {[0, 0.25, 0.5, 0.75, 1].map((t) => (
                <line key={'h' + t} x1="48" x2="402" y1={210 - t * 170} y2={210 - t * 170} />
              ))}
              {[0, 0.25, 0.5, 0.75, 1].map((t) => (
                <line key={'v' + t} y1="40" y2="210" x1={48 + t * 354} x2={48 + t * 354} />
              ))}
            </g>
            {frontierPoints.length > 1 ? (
              <>
                <polyline
                  className="pareto-line"
                  points={frontierPoints
                    .map((point) => point.x + ',' + point.y)
                    .join(' ')}
                />
              </>
            ) : null}
            {plotted.map(({ model, xValue, x, quality, y, frontier }, index) => {
              const selected = selectedModel === model.model_signature;
              const labelRight = x < 300;
              const labelY = y + (index % 2 === 0 ? -9 : 13);
              return (
                <g
                  key={model.model_signature}
                  className={
                    'scatter-point ' +
                    (model.deployment === 'local' ? 'local ' : 'api ') +
                    (selected ? 'selected ' : '') +
                    (frontier ? 'frontier' : '')
                  }
                  onClick={() => onSelect?.(model.model_signature)}
                >
                  <circle cx={x} cy={y} r={selected ? 7 : 5.5}>
                    <title>
                      {model.model_key + ' · quality ' + quality.toFixed(1) +
                        (xMetric === 'latency'
                          ? ' · P50 ' + milliseconds(xValue)
                          : ' · ' + usd(xValue) + ' / 1k cases')}
                    </title>
                  </circle>
                  <text
                    x={labelRight ? x + 9 : x - 9}
                    y={labelY}
                    textAnchor={labelRight ? 'start' : 'end'}
                  >
                    {shortModelLabel(model.model_key)}
                  </text>
                </g>
              );
            })}
            <text className="axis-label" x="8" y="30">100</text>
            <text className="axis-label" x="14" y="214">40</text>
            <text className="axis-title" x="190" y="242">
              {xMetric === 'latency' ? 'Observed latency · P50' : 'Known provider cost / 1k cases'}
            </text>
          </svg>
        </div>
      ) : (
        <div className="empty-visual">No comparable observed points yet.</div>
      )}
    </section>
  );
}

export function QualityLeaderboard({
  models,
  selectedModel,
  onSelect,
}: {
  models: DecisionModelSummary[];
  selectedModel?: string | null;
  onSelect?: (modelSignature: string) => void;
}) {
  const ranked = [...models].sort((a, b) => {
    if (a.quality_coverage_complete !== b.quality_coverage_complete) {
      return a.quality_coverage_complete ? -1 : 1;
    }
    return (b.overall_quality_score ?? -1) - (a.overall_quality_score ?? -1);
  });
  const max = Math.max(
    ...ranked.map((item) => item.overall_quality_score ?? 0),
    100,
  );
  return (
    <section className="analysis-card leaderboard-card">
      <div className="section-heading compact">
        <div>
          <h2>Overall quality</h2>
          <p>Equal-weight score across the selected comparable capability cohort.</p>
        </div>
        <span className="semantic-chip">policy v1</span>
      </div>
      <div className="leaderboard">
        {ranked.map((model, index) => (
          <button
            type="button"
            key={model.model_signature}
            className={
              selectedModel === model.model_signature
                ? 'leader-row selected'
                : 'leader-row'
            }
            onClick={() => onSelect?.(model.model_signature)}
          >
            <span className="rank">{index + 1}</span>
            <span className="leader-name">
              <strong>{model.model_key}</strong>
              <span>
                <DeploymentBadge deployment={model.deployment} />
                {!model.quality_coverage_complete ? (
                  <em>Partial coverage</em>
                ) : null}
              </span>
            </span>
            <span className="leader-bar">
              <i
                style={{
                  width:
                    ((model.overall_quality_score ?? 0) / max) * 100 + '%',
                }}
              />
            </span>
            <strong className="leader-score">{score(model.overall_quality_score)}</strong>
          </button>
        ))}
      </div>
    </section>
  );
}


type DatasetLandscapeView = 'score' | 'delta' | 'rank';
type DatasetLandscapeSort = 'discriminative' | 'hardest' | 'alphabetical';

interface DatasetLandscapeRow {
  capability_id: string;
  dataset_id: string;
  sample_count: number;
  best_score: number | null;
  worst_score: number | null;
  average_score: number | null;
  spread: number | null;
  winner_model_key: string | null;
  best_local_model_key: string | null;
  values: DecisionDatasetSummary[];
}

function buildDatasetLandscapeRows(
  datasets: DecisionDatasetSummary[],
  models: DecisionModelSummary[],
): DatasetLandscapeRow[] {
  const grouped = new Map<string, DecisionDatasetSummary[]>();
  datasets.forEach((row) => {
    const key = row.capability_id + '::' + row.dataset_id;
    grouped.set(key, [...(grouped.get(key) ?? []), row]);
  });
  const localKeys = new Set(
    models.filter((model) => model.deployment === 'local').map((model) => model.model_key),
  );
  return [...grouped.entries()].map(([key, values]) => {
    const scored = values.filter((row) => row.normalized_quality_score != null);
    const sorted = [...scored].sort(
      (a, b) => Number(b.normalized_quality_score) - Number(a.normalized_quality_score),
    );
    const local = sorted.find((row) => localKeys.has(row.model_key));
    const scores = scored.map((row) => Number(row.normalized_quality_score));
    const best = scores.length ? Math.max(...scores) : null;
    const worst = scores.length ? Math.min(...scores) : null;
    const [capability_id, dataset_id] = key.split('::');
    return {
      capability_id,
      dataset_id,
      sample_count: values[0]?.sample_count ?? 0,
      best_score: best,
      worst_score: worst,
      average_score: scores.length
        ? scores.reduce((total, value) => total + value, 0) / scores.length
        : null,
      spread: best != null && worst != null ? best - worst : null,
      winner_model_key: sorted[0]?.model_key ?? null,
      best_local_model_key: local?.model_key ?? null,
      values,
    };
  });
}

export function DatasetPerformanceLandscape({
  datasets,
  models,
}: {
  datasets: DecisionDatasetSummary[];
  models: DecisionModelSummary[];
}) {
  const [view, setView] = useState<DatasetLandscapeView>('score');
  const [sortMode, setSortMode] = useState<DatasetLandscapeSort>('discriminative');
  const rows = useMemo(
    () => buildDatasetLandscapeRows(datasets, models),
    [datasets, models],
  );
  const sortedRows = useMemo(() => {
    const result = [...rows];
    if (sortMode === 'hardest') {
      return result.sort(
        (a, b) => Number(a.average_score ?? 999) - Number(b.average_score ?? 999),
      );
    }
    if (sortMode === 'alphabetical') {
      return result.sort((a, b) => a.dataset_id.localeCompare(b.dataset_id));
    }
    return result.sort((a, b) => Number(b.spread ?? -1) - Number(a.spread ?? -1));
  }, [rows, sortMode]);

  const winCounts = new Map<string, number>();
  rows.forEach((row) => {
    if (row.winner_model_key) {
      winCounts.set(row.winner_model_key, (winCounts.get(row.winner_model_key) ?? 0) + 1);
    }
  });
  const mostWins = [...winCounts.entries()].sort((a, b) => b[1] - a[1])[0];
  const hardest = [...rows]
    .filter((row) => row.average_score != null)
    .sort((a, b) => Number(a.average_score) - Number(b.average_score))[0];
  const discriminative = [...rows]
    .filter((row) => row.spread != null)
    .sort((a, b) => Number(b.spread) - Number(a.spread))[0];
  const localWins = new Map<string, number>();
  rows.forEach((row) => {
    if (row.best_local_model_key) {
      localWins.set(
        row.best_local_model_key,
        (localWins.get(row.best_local_model_key) ?? 0) + 1,
      );
    }
  });
  const bestLocal = [...localWins.entries()].sort((a, b) => b[1] - a[1])[0];

  return (
    <section className="analysis-card dataset-landscape-card">
      <div className="section-heading">
        <div>
          <h2>Dataset performance landscape</h2>
          <p>See who wins where, how large each gap is and which datasets discriminate most.</p>
        </div>
        <div className="dataset-landscape-controls">
          <div className="segmented">
            {(['score', 'delta', 'rank'] as const).map((item) => (
              <button
                key={item}
                type="button"
                className={view === item ? 'active' : ''}
                onClick={() => setView(item)}
              >
                {item === 'score' ? 'Score' : item === 'delta' ? 'Delta vs best' : 'Rank'}
              </button>
            ))}
          </div>
          <select
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value as DatasetLandscapeSort)}
          >
            <option value="discriminative">Most discriminative</option>
            <option value="hardest">Hardest</option>
            <option value="alphabetical">Alphabetical</option>
          </select>
        </div>
      </div>

      <div className="dataset-insight-chips">
        <div><Trophy size={14}/><span>Most wins</span><strong>{mostWins ? mostWins[0] + ' · ' + mostWins[1] : '—'}</strong></div>
        <div><span>Best local</span><strong>{bestLocal ? bestLocal[0] : '—'}</strong></div>
        <div><span>Hardest</span><strong>{hardest?.dataset_id ?? '—'}</strong></div>
        <div><span>Most discriminative</span><strong>{discriminative?.dataset_id ?? '—'}</strong></div>
      </div>

      <div className="dataset-landscape-list">
        {sortedRows.map((row) => {
          const ranked = [...row.values]
            .filter((item) => item.normalized_quality_score != null)
            .sort(
              (a, b) =>
                Number(b.normalized_quality_score) - Number(a.normalized_quality_score),
            );
          const rankMap = new Map(ranked.map((item, index) => [item.model_key, index + 1]));
          return (
            <AppLink
              key={row.capability_id + row.dataset_id}
              href={'/datasets/' + encodeURIComponent(row.dataset_id)}
              className="dataset-landscape-row"
            >
              <div className="dataset-landscape-meta">
                <span>{row.capability_id.replaceAll('-', ' ')}</span>
                <strong>{row.dataset_id}</strong>
                <small>
                  winner {row.winner_model_key ?? '—'} · spread {row.spread?.toFixed(1) ?? '—'}
                </small>
              </div>
              <div className="dataset-landscape-track">
                {models.map((model, modelIndex) => {
                  const value = row.values.find((item) => item.model_key === model.model_key);
                  const scoreValue = value?.normalized_quality_score ?? null;
                  const delta =
                    scoreValue != null && row.best_score != null
                      ? scoreValue - row.best_score
                      : null;
                  const display =
                    view === 'rank'
                      ? rankMap.has(model.model_key) ? '#' + rankMap.get(model.model_key) : '—'
                      : view === 'delta'
                        ? delta == null ? '—' : delta === 0 ? 'best' : delta.toFixed(1)
                        : score(scoreValue);
                  return scoreValue == null ? null : (
                    <div
                      key={model.model_signature}
                      className={'dataset-landscape-point ' + model.deployment}
                      style={{
                        left: Math.max(0, Math.min(100, scoreValue)) + '%',
                        top: ((modelIndex + 1) / (models.length + 1)) * 100 + '%',
                      }}
                      title={model.model_key + ' · ' + display}
                    >
                      <i/>
                      <span>{display}</span>
                    </div>
                  );
                })}
              </div>
              <ChevronRight size={14}/>
            </AppLink>
          );
        })}
      </div>
    </section>
  );
}

export function DatasetDeltaSlopegraph({
  datasets,
  modelA,
  modelB,
}: {
  datasets: DecisionDatasetSummary[];
  modelA: DecisionModelSummary;
  modelB: DecisionModelSummary;
}) {
  const pairs = datasets
    .filter((row) => row.model_key === modelA.model_key)
    .map((a) => {
      const b = datasets.find(
        (row) =>
          row.model_key === modelB.model_key &&
          row.capability_id === a.capability_id &&
          row.dataset_id === a.dataset_id,
      );
      if (a.normalized_quality_score == null || b?.normalized_quality_score == null) {
        return null;
      }
      return {
        capability_id: a.capability_id,
        dataset_id: a.dataset_id,
        a: Number(a.normalized_quality_score),
        b: Number(b.normalized_quality_score),
        delta: Number(a.normalized_quality_score) - Number(b.normalized_quality_score),
      };
    })
    .filter((item): item is NonNullable<typeof item> => item != null)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

  const aWins = pairs.filter((pair) => pair.delta > 0.05).length;
  const bWins = pairs.filter((pair) => pair.delta < -0.05).length;
  const ties = pairs.filter((pair) => Math.abs(pair.delta) <= 0.05).length;
  const y = (value: number) => 7 + ((100 - value) / 60) * 30;

  return (
    <section className="analysis-card dataset-slope-card">
      <div className="section-heading">
        <div>
          <h2>Dataset delta slopegraph</h2>
          <p>Sorted by absolute gap. Each row shows where Model A gains or loses against Model B.</p>
        </div>
        <div className="slope-summary">
          <span><b>{aWins}</b> A wins</span>
          <span><b>{bWins}</b> B wins</span>
          <span><b>{ties}</b> ties</span>
        </div>
      </div>
      {pairs.length ? (
        <>
          <div className="slopegraph-column-head">
            <span>Dataset</span>
            <div><strong>{shortModelLabel(modelA.model_key)}</strong><small>Model A</small></div>
            <div><strong>{shortModelLabel(modelB.model_key)}</strong><small>Model B</small></div>
            <span>Δ A − B</span>
          </div>
          <div className="slopegraph-rows">
            {pairs.map((pair) => {
              const state =
                Math.abs(pair.delta) <= 0.05
                  ? 'tie'
                  : pair.delta > 0
                    ? 'a-win'
                    : 'b-win';
              return (
                <div
                  key={pair.capability_id + pair.dataset_id}
                  className={'slopegraph-row ' + state}
                >
                  <div className="slope-dataset-meta">
                    <strong>{pair.dataset_id}</strong>
                    <small>{pair.capability_id.replaceAll('-', ' ')}</small>
                  </div>
                  <div className="slope-mini">
                    <svg viewBox="0 0 420 44" role="img" aria-label={pair.dataset_id}>
                      <line className="slope-midline" x1="20" x2="400" y1="22" y2="22"/>
                      <line
                        className="slope-segment"
                        x1="24"
                        y1={y(pair.a)}
                        x2="396"
                        y2={y(pair.b)}
                      />
                      <circle className="slope-point-a" cx="24" cy={y(pair.a)} r="5"/>
                      <circle className="slope-point-b" cx="396" cy={y(pair.b)} r="5"/>
                      <text x="36" y={y(pair.a) + 3}>{score(pair.a)}</text>
                      <text x="384" y={y(pair.b) + 3} textAnchor="end">{score(pair.b)}</text>
                      <title>
                        {pair.dataset_id + ' · A ' + score(pair.a) + ' · B ' + score(pair.b)}
                      </title>
                    </svg>
                  </div>
                  <em className={state}>
                    {pair.delta > 0 ? '+' : ''}{pair.delta.toFixed(1)}
                  </em>
                </div>
              );
            })}
          </div>
          <div className="slope-legend">
            <span className="a-win">A advantage</span>
            <span className="b-win">B advantage</span>
            <span className="tie">Near tie</span>
          </div>
        </>
      ) : (
        <div className="empty-visual">No common dataset evidence for the selected models.</div>
      )}
    </section>
  );
}

export function DatasetHeatmap({
  datasets,
  models,
  view = 'score',
}: {
  datasets: DecisionDatasetSummary[];
  models: DecisionModelSummary[];
  view?: 'score' | 'delta' | 'rank';
}) {
  const modelKeys = models.map((model) => model.model_key);
  const rows = Array.from(
    new Map(
      datasets.map((row) => [
        row.capability_id + '::' + row.dataset_id,
        {
          capability_id: row.capability_id,
          dataset_id: row.dataset_id,
          sample_count: row.sample_count,
        },
      ]),
    ).values(),
  ).sort((a, b) =>
    (a.capability_id + a.dataset_id).localeCompare(
      b.capability_id + b.dataset_id,
    ),
  );

  const byCell = new Map(
    datasets.map((row) => [
      row.model_key + '::' + row.capability_id + '::' + row.dataset_id,
      row,
    ]),
  );

  return (
    <section className="analysis-card heatmap-card">
      <div className="section-heading compact">
        <div>
          <h2>Performance by dataset</h2>
          <p>Drill from capability into the datasets that explain the aggregate score.</p>
        </div>
        <span className="semantic-chip">{view === 'score' ? 'Score' : view}</span>
      </div>
      <div className="heatmap-scroll">
        <div
          className="heatmap-grid"
          style={{ '--model-count': modelKeys.length } as CSSProperties}
        >
          <div className="heatmap-head">Capability / dataset</div>
          <div className="heatmap-head samples">n</div>
          {models.map((model) => (
            <div className="heatmap-head model" key={model.model_signature}>
              <span>{model.model_key}</span>
              <DeploymentBadge deployment={model.deployment} />
            </div>
          ))}
          {rows.map((row) => {
            const available = modelKeys
              .map((modelKey) =>
                byCell.get(modelKey + '::' + row.capability_id + '::' + row.dataset_id),
              )
              .filter((value): value is DecisionDatasetSummary => Boolean(value));
            const scores = available
              .map((item) => item.normalized_quality_score)
              .filter((value): value is number => value != null);
            const best = scores.length ? Math.max(...scores) : null;
            const ranks = [...available]
              .sort(
                (a, b) =>
                  (b.normalized_quality_score ?? -1) -
                  (a.normalized_quality_score ?? -1),
              )
              .map((item, index) => [item.model_key, index + 1] as const);
            const rankMap = new Map(ranks);
            return (
              <div className="heatmap-row contents" key={row.capability_id + row.dataset_id}>
                <AppLink
                  href={'/datasets/' + encodeURIComponent(row.dataset_id)}
                  className="heatmap-label"
                >
                  <span>{row.capability_id.replaceAll('-', ' ')}</span>
                  <strong>{row.dataset_id}</strong>
                  <ChevronRight size={14} />
                </AppLink>
                <div className="heatmap-samples">{row.sample_count}</div>
                {modelKeys.map((modelKey) => {
                  const cell = byCell.get(
                    modelKey + '::' + row.capability_id + '::' + row.dataset_id,
                  );
                  const value = cell?.normalized_quality_score ?? null;
                  const delta =
                    value != null && best != null ? value - best : null;
                  const display =
                    view === 'rank'
                      ? cell
                        ? '#' + rankMap.get(modelKey)
                        : '—'
                      : view === 'delta'
                        ? delta == null
                          ? '—'
                          : delta === 0
                            ? 'best'
                            : delta.toFixed(1)
                        : score(value);
                  const heat = value == null ? 0 : Math.max(0, Math.min(1, value / 100));
                  return (
                    <div
                      key={modelKey}
                      className="heatmap-cell"
                      style={{ '--heat': heat } as CSSProperties}
                      title={
                        cell
                          ? [
                              modelKey,
                              'score ' + score(value),
                              'P50 ' + milliseconds(cell.latency_p50_ms),
                              cell.provider_cost_known
                                ? usd(cell.provider_cost_per_1k_cases_usd) + ' / 1k cases'
                                : 'provider cost N/A',
                            ].join(' · ')
                          : 'No CURRENT comparable result'
                      }
                    >
                      {display}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function MethodologyAccordion({
  policyLabel,
}: {
  policyLabel?: string;
}) {
  return (
    <div className="methodology-row" id="methodology">
      <details>
        <summary>
          <span><Sparkles size={17} /> Methodology</span>
          <small>Datasets, scoring and normalization</small>
        </summary>
        <p>
          Task-specific primary metrics remain authoritative. The overall quality
          index is a versioned navigation aid and never replaces capability-level
          evidence.
        </p>
      </details>
      <details>
        <summary>
          <span><Info size={17} /> CURRENT policy</span>
          <small>Latest valid comparable evidence</small>
        </summary>
        <p>
          Partial or failed runs remain visible in Runs, but never replace the
          latest valid completed comparable result.
        </p>
      </details>
      <details>
        <summary>
          <span><Info size={17} /> Quality policy</span>
          <small>{policyLabel ?? 'Explicit versioned aggregation'}</small>
        </summary>
        <p>
          Coverage is explicit. Models missing required capabilities are marked
          partial rather than silently receiving a zero.
        </p>
      </details>
    </div>
  );
}
