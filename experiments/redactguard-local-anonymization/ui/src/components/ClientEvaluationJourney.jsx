import { useEffect, useMemo, useState } from "react";
import { formatMs, formatPercent, micro } from "../utils/formatters";

const TYPE_LABELS = {
  private_person: "Personal names",
  private_email: "Email addresses",
  private_phone: "Phone numbers",
  private_address: "Addresses & locations",
  private_date: "Dates",
  account_number: "Financial & record identifiers",
  secret: "Secrets & credentials",
  health_condition: "Health conditions",
  treatment: "Treatments",
  lab_result: "Lab results",
  demographic: "Demographic data",
  personal_measurement: "Personal measurements",
  lifestyle: "Lifestyle information",
};

function typeLabel(type) {
  if (TYPE_LABELS[type]) return TYPE_LABELS[type];
  return String(type ?? "Sensitive data")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeValue(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim().toLocaleLowerCase();
}

function maskValue(value, type) {
  const raw = String(value ?? "").trim();
  if (!raw) return "••••";
  if (String(type).includes("email") && raw.includes("@")) {
    const [local, domain] = raw.split("@");
    return `${local.slice(0, 1)}••••@${domain}`;
  }
  if (String(type).includes("phone")) {
    const digits = raw.replace(/\D/g, "");
    return `•••• ${digits.slice(-4)}`.trim();
  }
  if (
    String(type).includes("account") ||
    String(type).includes("secret") ||
    raw.length > 20
  ) {
    return `${raw.slice(0, 3)}••••••••${raw.slice(-4)}`;
  }
  if (raw.length <= 4) {
    return `${raw.slice(0, 1)}${"•".repeat(Math.max(2, raw.length - 1))}`;
  }
  const prefix = Math.min(3, Math.max(1, Math.floor(raw.length / 4)));
  return `${raw.slice(0, prefix)}${"•".repeat(
    Math.min(8, Math.max(3, raw.length - prefix - 2)),
  )}${raw.slice(-2)}`;
}

function groupEntities(spans) {
  const grouped = new Map();
  for (const span of spans ?? []) {
    const key = `${span.pii_type}::${normalizeValue(span.value)}`;
    const current = grouped.get(key);
    if (current) {
      current.occurrences += 1;
    } else {
      grouped.set(key, {
        key,
        type: span.pii_type,
        label: typeLabel(span.pii_type),
        maskedValue: maskValue(span.value, span.pii_type),
        occurrences: 1,
      });
    }
  }
  return [...grouped.values()].sort(
    (left, right) =>
      right.occurrences - left.occurrences ||
      left.label.localeCompare(right.label),
  );
}

function summarizeTypes(spans) {
  const counts = new Map();
  for (const span of spans ?? []) {
    counts.set(span.pii_type, (counts.get(span.pii_type) ?? 0) + 1);
  }
  return counts;
}

function modelMetrics(detail, model) {
  const summary = micro(detail?.metrics?.[model]);
  const latency = micro(detail?.latency?.metrics?.[model]);
  return {
    model,
    recall: summary.pii_recall,
    leakage: summary.system_leakage_rate ?? summary.leakage_rate,
    qualityLeakage: summary.leakage_rate,
    precision: summary.precision,
    success: summary.inference_success_rate ?? summary.valid_output_rate,
    latency: latency.latency_p95_ms ?? summary.latency_p95_ms,
    evaluated: summary.evaluated_cases ?? summary.cases ?? 0,
    cases: summary.cases ?? 0,
    valid: summary.quality_available !== false,
  };
}

function metricTone(value, kind) {
  if (value === null || value === undefined) return "neutral";
  if (kind === "leakage") {
    if (value <= 0.01) return "positive";
    if (value <= 0.05) return "warning";
    return "risk";
  }
  if (kind === "recall" || kind === "precision" || kind === "success") {
    if (value >= 0.95) return "positive";
    if (value >= 0.85) return "warning";
    return "risk";
  }
  return "neutral";
}

function MetricValue({ value, kind = "percentage" }) {
  if (kind === "latency") return <>{formatMs(value)}</>;
  return <>{formatPercent(value)}</>;
}

function Breadcrumb({ level, documentName, model, onNavigate }) {
  return (
    <nav className="client-journey-breadcrumb" aria-label="Client evaluation breadcrumb">
      <button
        type="button"
        className={level === "overview" ? "current" : ""}
        onClick={() => onNavigate("overview")}
      >
        Model overview
      </button>
      {level !== "overview" ? (
        <>
          <span>›</span>
          <button
            type="button"
            className={level === "documents" ? "current" : ""}
            onClick={() => onNavigate("documents")}
          >
            Documents
          </button>
        </>
      ) : null}
      {level === "detail" ? (
        <>
          <span>›</span>
          <span className="current truncate">{documentName}</span>
          <span>›</span>
          <span className="current truncate">{model}</span>
        </>
      ) : null}
    </nav>
  );
}

function ClientEvaluationJourney({ detail, selectedModel, onSelectModel }) {
  const [level, setLevel] = useState("overview");
  const [selectedDocument, setSelectedDocument] = useState(null);

  const models = useMemo(
    () => detail?.summary?.models ?? Object.keys(detail?.metrics ?? {}),
    [detail],
  );
  const documents = useMemo(
    () => Object.keys(detail?.docSpans ?? {}).sort(),
    [detail],
  );

  useEffect(() => {
    if (selectedDocument && !documents.includes(selectedDocument)) {
      setSelectedDocument(null);
      setLevel("overview");
    }
  }, [documents, selectedDocument]);

  const effectiveModel =
    selectedModel && models.includes(selectedModel)
      ? selectedModel
      : models[0] ?? null;

  const openDocuments = (model = effectiveModel) => {
    if (model) onSelectModel?.(model);
    setLevel("documents");
  };

  const openDetail = (documentName, model) => {
    setSelectedDocument(documentName);
    onSelectModel?.(model);
    setLevel("detail");
  };

  const navigate = (target) => {
    if (target === "overview") {
      setSelectedDocument(null);
    }
    setLevel(target);
  };

  const goldCount = useMemo(
    () =>
      documents.reduce(
        (total, documentName) =>
          total + (detail?.docSpans?.[documentName]?.gold?.length ?? 0),
        0,
      ),
    [detail, documents],
  );

  return (
    <div className="client-journey">
      <header className="client-journey-header">
        <div>
          <span className="client-journey-kicker">PII detection evaluation</span>
          <h1>
            {level === "overview"
              ? "Model comparison"
              : level === "documents"
                ? "Document comparison"
                : "Document × model detail"}
          </h1>
          <p>
            {level === "overview"
              ? "Start with the overall benchmark. Open a model only when you need to understand where its results come from."
              : level === "documents"
                ? "Compare the same test document across every model, then drill into one result."
                : "Inspect one model on one document, including detected PII and the benchmark evidence behind the score."}
          </p>
        </div>
        <div className="client-journey-scope">
          <span>{models.length} models</span>
          <span>{documents.length} documents</span>
          <span>{goldCount} annotated PII</span>
        </div>
      </header>

      <Breadcrumb
        level={level}
        documentName={selectedDocument}
        model={effectiveModel}
        onNavigate={navigate}
      />

      {level === "overview" ? (
        <ModelOverview
          detail={detail}
          models={models}
          documents={documents}
          onOpenDocuments={openDocuments}
        />
      ) : level === "documents" ? (
        <DocumentMatrix
          detail={detail}
          models={models}
          documents={documents}
          onOpenDetail={openDetail}
        />
      ) : (
        <DocumentModelDetail
          detail={detail}
          models={models}
          documentName={selectedDocument}
          model={effectiveModel}
          onSelectModel={onSelectModel}
        />
      )}
    </div>
  );
}

function ModelOverview({ detail, models, documents, onOpenDocuments }) {
  const rows = models.map((model) => modelMetrics(detail, model));

  return (
    <section className="client-level">
      <div className="client-level-heading">
        <div>
          <span>Level 1</span>
          <h2>Overall benchmark results</h2>
        </div>
        <p>
          A small set of comparable metrics. No document-level detail until requested.
        </p>
      </div>

      <div className="client-model-comparison">
        <div className="client-model-comparison__head">
          <span>Model</span>
          <span>Recall</span>
          <span>Leakage</span>
          <span>Precision</span>
          <span>Success</span>
          <span>p95</span>
          <span />
        </div>

        {rows.map((row) => (
          <button
            type="button"
            className="client-model-row"
            key={row.model}
            onClick={() => onOpenDocuments(row.model)}
          >
            <div className="client-model-name">
              <strong>{row.model}</strong>
              <small>
                {row.evaluated}/{row.cases || documents.length} cases evaluated
              </small>
            </div>
            <strong className={`metric-text--${metricTone(row.recall, "recall")}`}>
              <MetricValue value={row.recall} />
            </strong>
            <strong className={`metric-text--${metricTone(row.leakage, "leakage")}`}>
              <MetricValue value={row.leakage} />
            </strong>
            <strong className={`metric-text--${metricTone(row.precision, "precision")}`}>
              <MetricValue value={row.precision} />
            </strong>
            <strong className={`metric-text--${metricTone(row.success, "success")}`}>
              <MetricValue value={row.success} />
            </strong>
            <strong>
              <MetricValue value={row.latency} kind="latency" />
            </strong>
            <span className="client-row-arrow">View documents →</span>
          </button>
        ))}
      </div>

      <aside className="client-context-note">
        <strong>How to read this view</strong>
        <span>
          Recall measures how much annotated PII was found. Leakage measures annotated
          PII characters left exposed. Precision measures how many resolved detections
          match the test annotations. Open a model to see the document-level evidence.
        </span>
      </aside>
    </section>
  );
}

function DocumentMatrix({ detail, models, documents, onOpenDetail }) {
  return (
    <section className="client-level">
      <div className="client-level-heading">
        <div>
          <span>Level 2</span>
          <h2>Where models differ</h2>
        </div>
        <p>
          Each row is one test document. Each model cell shows recall and the number of
          missed annotated PII spans.
        </p>
      </div>

      <div className="client-document-matrix-wrap">
        <table className="client-document-matrix">
          <thead>
            <tr>
              <th>Document</th>
              {models.map((model) => (
                <th key={model}>{model}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {documents.map((documentName) => {
              const document = detail?.docSpans?.[documentName];
              const firstMetrics = models
                .map((model) => detail?.metrics?.[model]?.by_document?.[documentName])
                .find(Boolean);
              return (
                <tr key={documentName}>
                  <td>
                    <div className="client-document-name">
                      <strong>{documentName}</strong>
                      <small>
                        {firstMetrics?.profile ?? "general"} · {document?.gold?.length ?? 0} annotated PII
                      </small>
                    </div>
                  </td>
                  {models.map((model) => {
                    const modelData = document?.models?.[model];
                    const docMetrics =
                      detail?.metrics?.[model]?.by_document?.[documentName];
                    const recall = modelData?.recall ?? docMetrics?.pii_recall ?? null;
                    const missed =
                      modelData?.missedCount ??
                      docMetrics?.fn ??
                      (modelData?.valid === false ? document?.gold?.length ?? 0 : 0);
                    const valid = modelData?.valid ?? docMetrics?.quality_available ?? false;

                    return (
                      <td key={model}>
                        <button
                          type="button"
                          className={`client-document-cell ${!valid ? "client-document-cell--invalid" : ""}`}
                          onClick={() => onOpenDetail(documentName, model)}
                        >
                          <strong
                            className={`metric-text--${metricTone(recall, "recall")}`}
                          >
                            {valid ? formatPercent(recall) : "N/A"}
                          </strong>
                          <small>
                            {valid
                              ? missed === 0
                                ? "No missed spans"
                                : `${missed} missed`
                              : "Inference unavailable"}
                          </small>
                        </button>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <aside className="client-context-note">
        <strong>Progressive disclosure</strong>
        <span>
          The matrix only answers “where should I look?”. Click any model/document cell
          to inspect the actual detections and benchmark evidence.
        </span>
      </aside>
    </section>
  );
}

function DocumentModelDetail({
  detail,
  models,
  documentName,
  model,
  onSelectModel,
}) {
  const document = detail?.docSpans?.[documentName];
  const modelData = document?.models?.[model];
  const docMetrics = detail?.metrics?.[model]?.by_document?.[documentName] ?? {};
  const gold = document?.gold ?? [];
  const detected = modelData?.redactions ?? [];
  const missed = modelData?.missed ?? [];
  const extra = modelData?.overRedacted ?? [];
  const detectedEntities = groupEntities(detected);
  const missedEntities = groupEntities(missed);
  const extraEntities = groupEntities(extra);

  const recall = modelData?.recall ?? docMetrics.pii_recall ?? null;
  const leakage = modelData?.leakage ?? docMetrics.leakage_rate ?? null;
  const precision = modelData?.precision ?? docMetrics.precision ?? null;
  const latency = docMetrics.latency_p95_ms ?? docMetrics.latency_p50_ms ?? null;
  const valid = modelData?.valid ?? docMetrics.quality_available ?? false;

  const goldByType = summarizeTypes(gold);
  const detectedGoldByType = summarizeTypes(modelData?.identified ?? []);
  const missedByType = summarizeTypes(missed);
  const allTypes = [...new Set([...goldByType.keys(), ...detectedGoldByType.keys(), ...missedByType.keys()])]
    .sort((left, right) => typeLabel(left).localeCompare(typeLabel(right)));

  return (
    <section className="client-level">
      <div className="client-detail-model-switcher">
        <span>Model</span>
        <div>
          {models.map((candidate) => (
            <button
              type="button"
              key={candidate}
              className={candidate === model ? "active" : ""}
              onClick={() => onSelectModel?.(candidate)}
            >
              {candidate}
            </button>
          ))}
        </div>
      </div>

      <div className="client-detail-heading">
        <div>
          <span className="client-journey-kicker">Level 3 · Detailed evidence</span>
          <h2>{documentName}</h2>
          <p>
            {docMetrics?.profile ?? "general"} profile · {model}
          </p>
        </div>
        <span className={`client-detail-status client-detail-status--${valid ? "valid" : "invalid"}`}>
          {valid ? "Valid inference" : "Inference unavailable"}
        </span>
      </div>

      <div className="client-detail-kpis">
        <DetailKpi label="Recall" value={formatPercent(recall)} tone={metricTone(recall, "recall")} />
        <DetailKpi label="Leakage" value={formatPercent(leakage)} tone={metricTone(leakage, "leakage")} />
        <DetailKpi label="Precision" value={formatPercent(precision)} tone={metricTone(precision, "precision")} />
        <DetailKpi
          label="Detected / annotated"
          value={valid ? `${modelData?.identifiedCount ?? 0} / ${gold.length}` : "—"}
          tone="neutral"
        />
      </div>

      <div className="client-detail-grid">
        <article className="client-detail-panel">
          <div className="client-detail-panel__heading">
            <div>
              <span>Coverage by PII type</span>
              <h3>What was found vs missed</h3>
            </div>
          </div>
          {allTypes.length ? (
            <div className="client-type-evidence">
              <div className="client-type-evidence__head">
                <span>Category</span>
                <span>Annotated</span>
                <span>Found</span>
                <span>Missed</span>
              </div>
              {allTypes.map((type) => (
                <div className="client-type-evidence__row" key={type}>
                  <strong>{typeLabel(type)}</strong>
                  <span>{goldByType.get(type) ?? 0}</span>
                  <span>{detectedGoldByType.get(type) ?? 0}</span>
                  <span className={(missedByType.get(type) ?? 0) > 0 ? "risk" : ""}>
                    {missedByType.get(type) ?? 0}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="client-empty-copy">No annotated PII categories for this document.</p>
          )}
        </article>

        <article className="client-detail-panel">
          <div className="client-detail-panel__heading">
            <div>
              <span>Model output</span>
              <h3>Detected sensitive items</h3>
            </div>
            <small>{detected.length} occurrences</small>
          </div>
          <EntityList
            items={detectedEntities}
            empty="No sensitive values were returned by this model."
          />
        </article>
      </div>

      <div className="client-detail-grid client-detail-grid--secondary">
        <article className={`client-detail-panel ${missed.length ? "client-detail-panel--attention" : ""}`}>
          <div className="client-detail-panel__heading">
            <div>
              <span>Benchmark evidence</span>
              <h3>Missed annotated PII</h3>
            </div>
            <small>{missed.length}</small>
          </div>
          <EntityList
            items={missedEntities}
            empty="No annotated PII spans were missed."
            attention
          />
        </article>

        <article className="client-detail-panel">
          <div className="client-detail-panel__heading">
            <div>
              <span>Benchmark evidence</span>
              <h3>Extra detections</h3>
            </div>
            <small>{extra.length}</small>
          </div>
          <EntityList
            items={extraEntities}
            empty="No unmatched resolved detections."
          />
        </article>
      </div>

      <details className="client-detail-more">
        <summary>More test details</summary>
        <div>
          <div>
            <span>Inference status</span>
            <strong>{modelData?.status ?? docMetrics?.representative_status ?? "—"}</strong>
          </div>
          <div>
            <span>Latency</span>
            <strong>{formatMs(latency)}</strong>
          </div>
          <div>
            <span>Gold spans</span>
            <strong>{gold.length}</strong>
          </div>
          <div>
            <span>Resolved redactions</span>
            <strong>{detected.length}</strong>
          </div>
        </div>
      </details>
    </section>
  );
}

function DetailKpi({ label, value, tone }) {
  return (
    <div className="client-detail-kpi">
      <span>{label}</span>
      <strong className={`metric-text--${tone}`}>{value}</strong>
    </div>
  );
}

function EntityList({ items, empty, attention = false }) {
  if (!items.length) {
    return <p className="client-detail-empty">{empty}</p>;
  }

  return (
    <div className="client-detail-entities">
      {items.slice(0, 12).map((item) => (
        <div className="client-detail-entity" key={item.key}>
          <div>
            <span>{item.label}</span>
            <strong>{item.maskedValue}</strong>
          </div>
          <small className={attention ? "attention" : ""}>
            {item.occurrences} occurrence{item.occurrences === 1 ? "" : "s"}
          </small>
        </div>
      ))}
      {items.length > 12 ? (
        <small className="client-detail-more-count">
          + {items.length - 12} more unique items
        </small>
      ) : null}
    </div>
  );
}

export default ClientEvaluationJourney;
