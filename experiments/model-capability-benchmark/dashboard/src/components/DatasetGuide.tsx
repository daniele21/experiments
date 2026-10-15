import { BookOpen, Info, Layers3, ShieldAlert } from 'lucide-react';
import { overview } from '../data';
import {
  activeDatasetGuides,
  datasetGuides,
  difficultyTotal,
  getDatasetGuide,
  getDatasetVersions,
  historicalDatasetGuides,
  type DatasetGuide as DatasetGuideRecord,
  type Difficulty,
} from '../datasetGuideData';
import { AppLink, PageHeader } from './Shell';

const difficultyLabels: Difficulty[] = ['easy', 'medium', 'hard', 'challenge'];

function DifficultyMix({ guide }: { guide: DatasetGuideRecord }) {
  const total = difficultyTotal(guide);
  if (!total) {
    return <span className="dataset-guide-note">No calibrated difficulty breakdown</span>;
  }
  return (
    <div className="dataset-guide-mix" aria-label="Authored difficulty distribution">
      <div className="dataset-guide-mix-bar" role="img"
        aria-label={difficultyLabels.filter(key => guide.difficulty?.[key]).map(key => key + ': ' + guide.difficulty?.[key]).join(', ')}>
        {difficultyLabels.map(key => {
          const count = guide.difficulty?.[key] ?? 0;
          return count ? <i key={key} className={'dataset-level-' + key} style={{ flexGrow: count }} /> : null;
        })}
      </div>
      <div className="dataset-guide-legend">
        {difficultyLabels.map(key => {
          const count = guide.difficulty?.[key] ?? 0;
          return count ? (
            <span key={key}><i className={'dataset-level-' + key} />{key} <strong>{count}</strong></span>
          ) : null;
        })}
      </div>
      <small>Author-assigned levels · not empirical model difficulty</small>
    </div>
  );
}

function FamilyMix({ guide }: { guide: DatasetGuideRecord }) {
  const families = guide.families ?? [];
  if (!families.length) {
    return <span className="dataset-guide-note">No per-family breakdown in this version</span>;
  }
  return (
    <div className="dataset-family-mix">
      <div className="dataset-family-segments" role="img"
        aria-label={families.map(family => family.label + ': ' + family.count).join(', ')}>
        {families.map((family, index) => (
          <i key={family.label} style={{ flexGrow: family.count }} className={'dataset-family-tone-' + (index % 6)} />
        ))}
      </div>
      <div className="dataset-family-legend">
        {families.map((family, index) => (
          <span key={family.label}>
            <i className={'dataset-family-tone-' + (index % 6)} />
            {family.label} <strong>{family.count}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

function Versions({ guide }: { guide: DatasetGuideRecord }) {
  const versions = getDatasetVersions(guide.group);
  if (versions.length < 2) return null;
  return (
    <div className="dataset-guide-versions" aria-label="Dataset versions">
      <span>Versions</span>
      {versions.map(version => (
        <AppLink key={version.id} href={'/datasets/' + encodeURIComponent(version.id)}
          className={version.id === guide.id ? 'is-selected' : ''}>
          v{version.version}
          {version.status === 'current' ? ' · active' : ''}
        </AppLink>
      ))}
    </div>
  );
}

function CatalogCard({ guide }: { guide: DatasetGuideRecord }) {
  return (
    <AppLink href={'/datasets/' + encodeURIComponent(guide.id)} className="dataset-catalog-card">
      <div className="dataset-card-topline">
        <span className="dataset-card-category">{guide.group}</span>
        <span className={'dataset-card-state ' + guide.status}>{guide.status === 'current' ? 'Active' : 'Historical'}</span>
      </div>
      <div className="dataset-card-title">
        <strong>{guide.name}</strong>
        <span>{guide.caseCount == null ? 'Public corpus' : guide.caseCount + ' authored cases'}</span>
      </div>
      <p>{guide.purpose}</p>
      {guide.difficulty ? <DifficultyMix guide={guide} /> :
        <div className="dataset-card-short-meta">{guide.metric}</div>}
      <span className="dataset-card-open">Explore scope & evidence →</span>
    </AppLink>
  );
}

export function DatasetCatalogPage() {
  const observedIds = [...new Set(overview.decision?.dataset_summaries.map(row => row.dataset_id) ?? [])];
  const unrecognizedIds = observedIds.filter(id => !getDatasetGuide(id));
  return (
    <>
      <PageHeader eyebrow="Benchmark literacy" title="Dataset guide"
        description="What each benchmark measures, how cases are distributed, and when scores are comparable." />
      <section className="dataset-catalog-intro">
        <BookOpen size={19} aria-hidden="true" />
        <span><strong>Read a score in context.</strong> A higher score only means more correct outcomes on the same tasks, cases and evaluation setup—not universal model quality.</span>
      </section>
      <div className="section-heading">
        <div><h2>Current suite</h2><p>{activeDatasetGuides.length} active datasets · historical versions remain available below.</p></div>
      </div>
      <section className="dataset-catalog-grid">
        {activeDatasetGuides.map(guide => <CatalogCard key={guide.id} guide={guide} />)}
        {unrecognizedIds.map(id => (
          <AppLink key={id} href={'/datasets/' + encodeURIComponent(id)} className="dataset-catalog-card">
            <div className="dataset-card-topline"><span className="dataset-card-category">Additional dataset</span></div>
            <strong>{id}</strong><p>Observed benchmark data. No authored guide is available yet.</p>
            <span className="dataset-card-open">Open results →</span>
          </AppLink>
        ))}
      </section>
      <details className="dataset-catalog-archive">
        <summary><Layers3 size={15} aria-hidden="true" /> Historical versions <span>{historicalDatasetGuides.length} preserved · compare within each version</span></summary>
        <div className="dataset-catalog-grid">
          {historicalDatasetGuides.map(guide => <CatalogCard key={guide.id} guide={guide} />)}
        </div>
      </details>
      <p className="dataset-guide-global-caution"><ShieldAlert size={15} aria-hidden="true" /> Cross-version scores must not be treated as longitudinal model improvements or regressions. Match dataset, case selection, seed, evaluator and generation settings.</p>
    </>
  );
}

export function DatasetContextPanel({ datasetId, primaryMetric, sampleCount }: {
  datasetId: string;
  primaryMetric?: string;
  sampleCount?: number;
}) {
  const guide = getDatasetGuide(datasetId);
  if (!guide) return (
    <section className="dataset-guide-detail dataset-guide-unknown">
      <Info size={17} aria-hidden="true" />
      <div><strong>No dataset description registered</strong><p>Evidence can still be explored. Do not infer task scope or dataset size from the displayed sample count.</p></div>
      <AppLink href="/datasets">All datasets →</AppLink>
    </section>
  );
  const siblings = datasetGuides.filter(item => item.group === guide.group);
  return (
    <section className="dataset-guide-detail" aria-label="Dataset explanation">
      <div className="dataset-guide-head">
        <div>
          <span className="dataset-guide-eyebrow">What this benchmark tests</span>
          <h2>{guide.purpose}</h2>
          <p>{guide.measures}</p>
        </div>
        <div className="dataset-guide-head-meta">
          <span className={'dataset-card-state ' + guide.status}>{guide.status === 'current' ? 'Active' : 'Historical'}</span>
          <AppLink href="/datasets">All datasets ↗</AppLink>
        </div>
      </div>
      <div className="dataset-guide-facts">
        <div><span>Corpus</span><strong>{guide.caseCount == null ? 'Public · variable selection' : guide.caseCount + ' cases'}</strong></div>
        <div><span>Core benchmark</span><strong>{guide.tiers ? guide.tiers.core + ' selected' : 'See run manifest'}</strong></div>
        <div><span>Scoring</span><strong>{primaryMetric ?? guide.metric}</strong></div>
        <div><span>Measured in run</span><strong>{sampleCount == null ? 'No current results' : sampleCount + ' cases / model'}</strong></div>
      </div>
      <div className="dataset-guide-detail-columns">
        <div>
          <span className="dataset-guide-subtitle">Case composition</span>
          <FamilyMix guide={guide} />
        </div>
        <div>
          <span className="dataset-guide-subtitle">Difficulty mix</span>
          <DifficultyMix guide={guide} />
        </div>
        <div className="dataset-guide-example">
          <span className="dataset-guide-subtitle">Illustrative example <small>· not a scored sample</small></span>
          <p>{guide.example.input}</p>
          <div><span>Expected</span><code>{guide.example.output}</code></div>
        </div>
      </div>
      <div className="dataset-guide-footer">
        <div><ShieldAlert size={15} aria-hidden="true" /><span>{guide.caution}</span></div>
        {guide.tiers ? <span className="dataset-guide-tier">Smoke {guide.tiers.smoke} · Core {guide.tiers.core} · Extended {guide.tiers.extended}</span> : null}
      </div>
      {siblings.length > 1 ? <Versions guide={guide} /> : null}
    </section>
  );
}
