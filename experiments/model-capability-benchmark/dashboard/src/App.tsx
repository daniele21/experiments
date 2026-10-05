import {
  Activity,
  BarChart3,
  Boxes,
  GitCompareArrows,
  History,
  Layers3,
  Share2,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import overviewFixture from './data/overview.fixture.json';
import capabilityFixture from './data/structured-output.fixture.json';
import { navigate, usePathname } from './router';
import type {
  CapabilityPayload,
  Disagreement,
  OverviewPayload,
} from './types';

declare global {
  interface Window {
    __MCB_OVERVIEW__?: OverviewPayload;
    __MCB_CAPABILITY__?: CapabilityPayload;
  }
}

const overview =
  (window.__MCB_OVERVIEW__ ?? overviewFixture) as OverviewPayload;
const capability =
  (window.__MCB_CAPABILITY__ ?? capabilityFixture) as CapabilityPayload;

function percent(value: number | null): string {
  return value === null ? '—' : (value * 100).toFixed(1) + '%';
}

function points(value: number | null): string {
  if (value === null) return '—';
  const sign = value > 0 ? '+' : '';
  return sign + (value * 100).toFixed(1) + ' pp';
}

function Link({
  href,
  children,
  className,
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <a
      href={href}
      className={className}
      onClick={(event) => {
        if (
          event.button === 0 &&
          !event.metaKey &&
          !event.ctrlKey &&
          !event.shiftKey
        ) {
          event.preventDefault();
          navigate(href);
        }
      }}
    >
      {children}
    </a>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const navigation = [
    ['/overview', BarChart3, 'Overview'],
    ['/models', Boxes, 'Models'],
    ['/capabilities/structured-output', Layers3, 'Capabilities'],
    ['/runs', Activity, 'Runs'],
    ['/compare', GitCompareArrows, 'Compare'],
    ['/share', Share2, 'Share'],
  ] as const;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">M</div>
          <span>MCB</span>
        </div>
        <nav>
          {navigation.map(([href, Icon, label]) => (
            <Link
              key={href}
              href={href}
              className={
                pathname === href ||
                (href.includes('capabilities') &&
                  pathname.startsWith('/capabilities'))
                  ? 'nav-item active'
                  : 'nav-item'
              }
            >
              <Icon size={17} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          <History size={15} />
          <span>Latest comparable</span>
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}

function FixtureBanner() {
  if (!overview.fixture) return null;
  return (
    <div className="fixture-banner">
      Fixture data · MCB-11 vertical slice · UI contract preview
    </div>
  );
}

function OverviewPage() {
  const cellsByCapability = useMemo(() => {
    const map = new Map<string, typeof overview.cells>();
    for (const cell of overview.cells) {
      map.set(cell.capability_id, [
        ...(map.get(cell.capability_id) ?? []),
        cell,
      ]);
    }
    return map;
  }, []);

  return (
    <>
      <FixtureBanner />
      <header className="page-header">
        <div>
          <div className="eyebrow">Latest comparable results</div>
          <h1>Model Capability Benchmark</h1>
          <p>
            Vertical model evaluation with immutable evidence and paired
            same-case comparisons.
          </p>
        </div>
        <div className="header-tags">
          <span>MCB v2</span>
          <span>core</span>
          <span>CURRENT only</span>
        </div>
      </header>

      <section className="card">
        <div className="section-heading">
          <div>
            <h2>Capability matrix</h2>
            <p>
              No overall score. Each row keeps its task-specific primary
              metric.
            </p>
          </div>
          <span className="status-chip good">Comparable</span>
        </div>
        <div className="matrix">
          <div className="matrix-row matrix-head">
            <div>Capability</div>
            {overview.models.map((model) => (
              <div key={model.model_signature}>{model.model_key}</div>
            ))}
          </div>
          {overview.capabilities.map((capabilityId) => {
            const cells = cellsByCapability.get(capabilityId) ?? [];
            return (
              <Link
                key={capabilityId}
                href={'/capabilities/' + capabilityId}
                className="matrix-row matrix-link"
              >
                <div>
                  <strong>{capabilityId}</strong>
                  <span>exact same benchmark signature</span>
                </div>
                {overview.models.map((model) => {
                  const cell = cells.find(
                    (item) => item.model_key === model.model_key,
                  );
                  return (
                    <div className="metric-cell" key={model.model_signature}>
                      <strong>{percent(cell?.primary_value ?? null)}</strong>
                      <span>
                        n={cell?.sample_count ?? 0} · failures=
                        {cell?.failure_count ?? 0}
                      </span>
                    </div>
                  );
                })}
              </Link>
            );
          })}
        </div>
      </section>

      <div className="two-col">
        <section className="card">
          <div className="section-heading">
            <div>
              <h2>Why this is CURRENT</h2>
              <p>Latest valid completed evidence wins inside each lineage.</p>
            </div>
          </div>
          <div className="timeline-mini">
            <div>
              <span className="dot current" />
              <strong>Oct 5 · completed</strong>
              <em>CURRENT</em>
            </div>
            <div>
              <span className="dot" />
              <strong>Oct 3 · completed</strong>
              <em>HISTORICAL</em>
            </div>
            <div>
              <span className="dot partial" />
              <strong>Oct 5 · newer partial</strong>
              <em>PARTIAL · excluded</em>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="section-heading">
            <div>
              <h2>Evidence contract</h2>
              <p>The UI is a projection, never the source of truth.</p>
            </div>
          </div>
          <div className="evidence-flow">
            <span>JSONL + manifest</span>
            <i>→</i>
            <span>DuckDB</span>
            <i>→</i>
            <span>typed JSON</span>
            <i>→</i>
            <span>UI</span>
          </div>
        </section>
      </div>
    </>
  );
}

function CapabilityPage() {
  const comparison = capability.comparison;
  const families = Array.from(
    new Set(capability.family_breakdown.map((row) => row.family)),
  );

  return (
    <>
      <FixtureBanner />
      <header className="page-header">
        <div>
          <div className="eyebrow">Capability detail</div>
          <h1>Structured output</h1>
          <p>
            Exact-match quality, paired comparison and failure-family
            breakdown.
          </p>
        </div>
        <Link
          href="/capabilities/structured-output/disagreements"
          className="primary-button"
        >
          Explore disagreements
        </Link>
      </header>

      <div className="hero-grid">
        {capability.cells.map((cell) => (
          <section className="score-card" key={cell.model_signature}>
            <span>{cell.model_key}</span>
            <strong>{percent(cell.primary_value)}</strong>
            <small>
              {Math.round((cell.primary_value ?? 0) * cell.sample_count)}
              {' / '}
              {cell.sample_count} correct
            </small>
          </section>
        ))}
        <section className="score-card comparison-card">
          <span>Paired delta</span>
          <strong>{points(comparison?.delta_b_minus_a ?? null)}</strong>
          <small>
            95% CI [{points(comparison?.ci95_low ?? null)}, {' '}
            {points(comparison?.ci95_high ?? null)}] · paired n=
            {comparison?.paired_count ?? '—'}
          </small>
        </section>
      </div>

      <section className="card">
        <div className="section-heading">
          <div>
            <h2>Performance by family</h2>
            <p>
              The aggregate gap is decomposed into controlled failure modes.
            </p>
          </div>
        </div>
        <div className="family-table">
          <div className="family-row family-head">
            <div>Family</div>
            {capability.cells.map((cell) => (
              <div key={cell.model_key}>{cell.model_key}</div>
            ))}
          </div>
          {families.map((family) => (
            <div className="family-row" key={family}>
              <div><strong>{family}</strong></div>
              {capability.cells.map((cell) => {
                const row = capability.family_breakdown.find(
                  (item) =>
                    item.family === family &&
                    item.model_key === cell.model_key,
                );
                return (
                  <div key={cell.model_key}>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{ width: percent(row?.value ?? null) }}
                      />
                    </div>
                    <span>{percent(row?.value ?? null)}</span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </section>

      <section className="card methodology-strip">
        <div>
          <strong>Same benchmark signature</strong>
          <span>{capability.benchmark_signatures[0]}</span>
        </div>
        <div>
          <strong>McNemar p</strong>
          <span>{comparison?.mcnemar_exact_p?.toFixed(4) ?? '—'}</span>
        </div>
        <div>
          <strong>Practical Δ</strong>
          <span>{points(comparison?.practical_delta ?? null)}</span>
        </div>
      </section>
    </>
  );
}

function OutcomeBadge({ outcome }: { outcome: Disagreement['outcome'] }) {
  const labels: Record<Disagreement['outcome'], string> = {
    both_correct: 'Both correct',
    a_only_correct: 'A only',
    b_only_correct: 'B only',
    both_wrong: 'Both wrong',
    pipeline_failure: 'Pipeline failure',
  };
  return <span className={'outcome ' + outcome}>{labels[outcome]}</span>;
}

function DisagreementsPage() {
  const [filter, setFilter] = useState<Disagreement['outcome'] | 'all'>(
    'all',
  );
  const items = capability.disagreements.filter(
    (item) => filter === 'all' || item.outcome === filter,
  );

  return (
    <>
      <FixtureBanner />
      <header className="page-header">
        <div>
          <div className="eyebrow">Failure analysis</div>
          <h1>Disagreement explorer</h1>
          <p>
            Only paired valid evaluations become quality disagreements.
            Pipeline failures stay separate.
          </p>
        </div>
        <Link
          href="/capabilities/structured-output"
          className="secondary-button"
        >
          Back to capability
        </Link>
      </header>

      <div className="filter-row">
        {(
          [
            ['all', 'All'],
            ['b_only_correct', 'GPT only correct'],
            ['a_only_correct', 'Qwen only correct'],
            ['both_wrong', 'Both wrong'],
            ['pipeline_failure', 'Pipeline failures'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            className={filter === value ? 'filter active' : 'filter'}
            onClick={() => setFilter(value)}
            type="button"
          >
            {label}
          </button>
        ))}
      </div>

      <div className="disagreement-layout">
        <section className="case-list card">
          {items.map((item) => (
            <div className="case-item" key={item.sample_id}>
              <div>
                <strong>{item.sample_id}</strong>
                <span>{item.family} · {item.difficulty}</span>
              </div>
              <OutcomeBadge outcome={item.outcome} />
            </div>
          ))}
        </section>

        <section className="case-detail card">
          {items[0] ? (
            <>
              <div className="section-heading">
                <div>
                  <div className="eyebrow">{items[0].family}</div>
                  <h2>{items[0].sample_id}</h2>
                </div>
                <OutcomeBadge outcome={items[0].outcome} />
              </div>
              <div className="case-columns">
                <article>
                  <span>Expected contract</span>
                  <pre>{'{\n  "merchant": "Fitzone",\n  "amount": 29.80,\n  "currency": "EUR",\n  "category": "fitness"\n}'}</pre>
                </article>
                <article className="wrong-panel">
                  <span>{items[0].model_a}</span>
                  <pre>{'{\n  "merchant": "gym",\n  "amount": 29,\n  "currency": "EUR"\n}'}</pre>
                  <small>Incorrect · missing normalized fields</small>
                </article>
                <article className="right-panel">
                  <span>{items[0].model_b}</span>
                  <pre>{'{\n  "merchant": "Fitzone",\n  "amount": 29.80,\n  "currency": "EUR",\n  "category": "fitness"\n}'}</pre>
                  <small>Correct</small>
                </article>
              </div>
              <div className="raw-note">
                Raw evidence remains referenced by case ID and attempt; it
                is loaded only on drill-down.
              </div>
            </>
          ) : (
            <p>No cases match this filter.</p>
          )}
        </section>
      </div>
    </>
  );
}

function SharePage() {
  const comparison = capability.comparison;
  const first = capability.cells[0];
  const second = capability.cells[1];
  const families = Array.from(
    new Set(capability.family_breakdown.map((row) => row.family)),
  );

  return (
    <>
      <FixtureBanner />
      <header className="page-header">
        <div>
          <div className="eyebrow">Immutable share snapshot</div>
          <h1>LinkedIn result card</h1>
          <p>
            This layout is intentionally separate from the analytical
            dashboard and is rendered from frozen snapshot data.
          </p>
        </div>
      </header>

      <div className="share-workspace">
        <aside className="share-options card">
          <strong>Template</strong>
          <button type="button" className="share-option active">
            Result comparison
          </button>
          <button type="button" className="share-option">
            Capability deep dive
          </button>
          <button type="button" className="share-option">
            Efficiency comparison
          </button>
          <button type="button" className="share-option">
            Methodology
          </button>
          <span>
            Production snapshots are created with
            <code> model-bench share create </code>
            and never follow live CURRENT results afterward.
          </span>
        </aside>

        <section className="linkedin-card">
          <div className="share-brand">MCB · Model Capability Benchmark</div>
          <h2>Can a 2B local model replace GPT for structured output?</h2>
          <div className="share-score-grid">
            <div>
              <span>{first?.model_key}</span>
              <strong>{percent(first?.primary_value ?? null)}</strong>
              <small>Local · Q4KM</small>
            </div>
            <div className="share-vs">vs</div>
            <div>
              <span>{second?.model_key}</span>
              <strong>{percent(second?.primary_value ?? null)}</strong>
              <small>API</small>
            </div>
          </div>
          <div className="share-delta">
            Δ {points(comparison?.delta_b_minus_a ?? null)}
            <small>
              95% CI [{points(comparison?.ci95_low ?? null)}, {' '}
              {points(comparison?.ci95_high ?? null)}] · paired n=
              {comparison?.paired_count ?? '—'}
            </small>
          </div>
          <div className="share-families">
            {families.map((family) => {
              const a = capability.family_breakdown.find(
                (row) => row.family === family && row.model_key === first?.model_key,
              );
              const b = capability.family_breakdown.find(
                (row) => row.family === family && row.model_key === second?.model_key,
              );
              return (
                <div className="share-family" key={family}>
                  <span>{family}</span>
                  <div>
                    <i style={{ width: percent(a?.value ?? null) }} />
                  </div>
                  <em>{percent(a?.value ?? null)}</em>
                  <div>
                    <i style={{ width: percent(b?.value ?? null) }} />
                  </div>
                  <em>{percent(b?.value ?? null)}</em>
                </div>
              );
            })}
          </div>
          <footer>
            MCB v2 · core · n=60 · same-case paired benchmark · fixture snapshot
          </footer>
        </section>
      </div>
    </>
  );
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <>
      <FixtureBanner />
      <header className="page-header">
        <div>
          <div className="eyebrow">MCB-11 vertical slice</div>
          <h1>{title}</h1>
          <p>This route is reserved by the new dashboard contract.</p>
        </div>
      </header>
      <section className="card empty-state">
        Implementation follows after the first comparable-result vertical
        slice is validated.
      </section>
    </>
  );
}

export function App() {
  const pathname = usePathname();

  let page: ReactNode;
  if (pathname === '/' || pathname === '/overview') {
    page = <OverviewPage />;
  } else if (
    pathname === '/capabilities/structured-output/disagreements'
  ) {
    page = <DisagreementsPage />;
  } else if (pathname === '/capabilities/structured-output') {
    page = <CapabilityPage />;
  } else if (pathname === '/models') {
    page = <PlaceholderPage title="Models" />;
  } else if (pathname === '/runs') {
    page = <PlaceholderPage title="Runs" />;
  } else if (pathname === '/compare') {
    page = <PlaceholderPage title="Compare" />;
  } else if (pathname === '/share' || pathname.startsWith('/share/')) {
    page = <SharePage />;
  } else {
    page = <PlaceholderPage title="Not found" />;
  }

  return <Shell>{page}</Shell>;
}
