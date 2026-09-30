import { useEffect, useMemo, useState } from "react";
import { formatPercent } from "../utils/formatters";

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

function labelForType(type) {
  if (TYPE_LABELS[type]) return TYPE_LABELS[type];
  return String(type ?? "Sensitive data")
    .replaceAll("_", " ")
    .replace(/w/g, (char) => char.toUpperCase());
}

function normalizeValue(value) {
  return String(value ?? "").replace(/s+/g, " ").trim().toLocaleLowerCase();
}

function maskValue(value, type) {
  const raw = String(value ?? "").trim();
  if (!raw) return "••••";

  if (String(type).includes("email") && raw.includes("@")) {
    const [local, domain] = raw.split("@");
    return `${local.slice(0, 1)}••••@${domain}`;
  }

  if (String(type).includes("phone")) {
    const digits = raw.replace(/D/g, "");
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

  const visiblePrefix = Math.min(3, Math.max(1, Math.floor(raw.length / 4)));
  return `${raw.slice(0, visiblePrefix)}${"•".repeat(
    Math.min(8, Math.max(3, raw.length - visiblePrefix - 2)),
  )}${raw.slice(-2)}`;
}

function aggregateDetectedItems(redactions) {
  const byEntity = new Map();

  for (const finding of redactions ?? []) {
    const key = `${finding.pii_type}::${normalizeValue(finding.value)}`;
    const existing = byEntity.get(key);
    if (existing) {
      existing.occurrences += 1;
      continue;
    }

    byEntity.set(key, {
      key,
      type: finding.pii_type,
      label: labelForType(finding.pii_type),
      maskedValue: maskValue(finding.value, finding.pii_type),
      occurrences: 1,
    });
  }

  return [...byEntity.values()].sort(
    (left, right) =>
      right.occurrences - left.occurrences ||
      left.label.localeCompare(right.label) ||
      left.maskedValue.localeCompare(right.maskedValue),
  );
}

function categoryBreakdown(items) {
  const counts = new Map();
  for (const item of items) {
    const current = counts.get(item.type) ?? {
      type: item.type,
      label: item.label,
      occurrences: 0,
      uniqueItems: 0,
    };
    current.occurrences += item.occurrences;
    current.uniqueItems += 1;
    counts.set(item.type, current);
  }
  return [...counts.values()].sort(
    (left, right) => right.occurrences - left.occurrences,
  );
}

function statusForModel(modelData) {
  if (!modelData) {
    return {
      tone: "neutral",
      label: "No evidence",
      title: "No result available",
      description: "This model has no evidence for the selected document.",
    };
  }

  if (!modelData.valid) {
    return {
      tone: "risk",
      label: "Needs attention",
      title: "Analysis could not be completed",
      description:
        "The document did not produce a valid structured detection result. No protection outcome should be inferred.",
    };
  }

  if ((modelData.redactionsCount ?? 0) === 0) {
    return {
      tone: "neutral",
      label: "Analysis complete",
      title: "No sensitive data detected",
      description:
        "The analysis completed successfully and returned no PII findings. Human review is still recommended before sharing.",
    };
  }

  return {
    tone: "positive",
    label: "Analysis complete",
    title: "Sensitive data detected",
    description:
      "The analysis completed successfully. The items below are the sensitive values proposed for redaction.",
  };
}

function ClientMetric({ label, value, hint }) {
  return (
    <div className="client-output-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </div>
  );
}

function ClientOutputPreview({
  detail,
  selectedModel,
  onSelectModel,
}) {
  const documents = useMemo(
    () => Object.keys(detail?.docSpans ?? {}).sort(),
    [detail],
  );
  const [selectedDocument, setSelectedDocument] = useState(documents[0] ?? null);
  const [showAllItems, setShowAllItems] = useState(false);
  const [showBenchmarkTruth, setShowBenchmarkTruth] = useState(true);

  useEffect(() => {
    if (!selectedDocument || !documents.includes(selectedDocument)) {
      setSelectedDocument(documents[0] ?? null);
    }
  }, [documents, selectedDocument]);

  useEffect(() => {
    setShowAllItems(false);
  }, [selectedDocument, selectedModel]);

  if (!documents.length) {
    return (
      <div className="empty-state large">
        <strong>No document evidence available</strong>
        <span>
          Run the realistic comparison first. Client Output Preview uses the
          actual findings stored in the benchmark JSONL evidence.
        </span>
      </div>
    );
  }

  const document = detail.docSpans?.[selectedDocument];
  const availableModels = Object.keys(document?.models ?? {}).sort();
  const effectiveModel =
    selectedModel && availableModels.includes(selectedModel)
      ? selectedModel
      : availableModels[0] ?? null;

  const modelData = effectiveModel ? document?.models?.[effectiveModel] : null;
  const docMetrics =
    effectiveModel && selectedDocument
      ? detail?.metrics?.[effectiveModel]?.by_document?.[selectedDocument]
      : null;

  const detectedItems = aggregateDetectedItems(modelData?.redactions ?? []);
  const categories = categoryBreakdown(detectedItems);
  const detectedOccurrences = detectedItems.reduce(
    (total, item) => total + item.occurrences,
    0,
  );
  const maxCategory = Math.max(
    1,
    ...categories.map((category) => category.occurrences),
  );
  const status = statusForModel(modelData);
  const visibleItems = showAllItems ? detectedItems : detectedItems.slice(0, 10);

  const profile =
    docMetrics?.profile ??
    Object.values(detail?.metrics ?? {})
      .map((summary) => summary?.by_document?.[selectedDocument]?.profile)
      .find(Boolean) ??
    "general";

  const benchmark = {
    recall: modelData?.recall ?? docMetrics?.pii_recall ?? null,
    precision: modelData?.precision ?? docMetrics?.precision ?? null,
    leakage: modelData?.leakage ?? docMetrics?.leakage_rate ?? null,
    missed: modelData?.missedCount ?? docMetrics?.fn ?? 0,
    overRedacted: modelData?.overRedactedCount ?? docMetrics?.fp ?? 0,
    gold: document?.gold?.length ?? docMetrics?.gold_count ?? 0,
  };

  return (
    <div className="client-output-workspace">
      <header className="client-output-toolbar no-print">
        <div>
          <span className="kicker">Product UX experiment</span>
          <h2>Client-facing PII recognition output</h2>
          <p>
            What a client could see after local PII detection — driven by the
            real findings of the selected benchmark run.
          </p>
        </div>

        <div className="client-output-selectors">
          <label>
            <span>Document</span>
            <select
              value={selectedDocument ?? ""}
              onChange={(event) => setSelectedDocument(event.target.value)}
            >
              {documents.map((documentName) => (
                <option key={documentName} value={documentName}>
                  {documentName}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Detection model</span>
            <select
              value={effectiveModel ?? ""}
              onChange={(event) => onSelectModel?.(event.target.value)}
            >
              {availableModels.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      <article className="client-report-preview">
        <header className="client-report-preview__header">
          <div>
            <div className="client-report-brand">RedactGuard</div>
            <span className="client-report-eyebrow">Sensitive data analysis</span>
            <h1>{selectedDocument}</h1>
            <p>{profile} policy</p>
          </div>
          <div className="client-report-local-badge">◉ Processed locally</div>
        </header>

        <div className="client-report-preview__body">
          <section
            className={`client-analysis-status client-analysis-status--${status.tone}`}
          >
            <div>
              <span>{status.label}</span>
              <strong>{status.title}</strong>
              <p>{status.description}</p>
            </div>
            <div className="client-analysis-status__count">
              <strong>{detectedOccurrences}</strong>
              <span>PII occurrences detected</span>
            </div>
          </section>

          <section className="client-output-metrics">
            <ClientMetric
              label="Sensitive items"
              value={detectedItems.length}
              hint="Unique detected values"
            />
            <ClientMetric
              label="Occurrences"
              value={detectedOccurrences}
              hint="Detected source spans"
            />
            <ClientMetric
              label="Categories"
              value={categories.length}
              hint="Sensitive data types"
            />
            <ClientMetric
              label="Suggested redactions"
              value={modelData?.valid ? detectedOccurrences : "—"}
              hint="Pending human review"
            />
          </section>

          <section className="client-output-grid">
            <div className="client-report-section">
              <div className="client-report-section__heading">
                <div>
                  <span className="client-report-eyebrow">
                    Sensitive data footprint
                  </span>
                  <h3>What was detected</h3>
                </div>
                <span>{categories.length} categories</span>
              </div>

              {categories.length ? (
                <div className="client-category-list">
                  {categories.map((category) => (
                    <div className="client-category-row" key={category.type}>
                      <div>
                        <strong>{category.label}</strong>
                        <small>{category.uniqueItems} unique items</small>
                      </div>
                      <div className="client-category-row__bar">
                        <span
                          style={{
                            width: `${(category.occurrences / maxCategory) * 100}%`,
                          }}
                        />
                      </div>
                      <b>{category.occurrences}</b>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="client-empty-copy">
                  No sensitive categories were returned by this analysis.
                </p>
              )}
            </div>

            <div className="client-report-section">
              <div className="client-report-section__heading">
                <div>
                  <span className="client-report-eyebrow">Review queue</span>
                  <h3>Detected sensitive items</h3>
                </div>
                <span>Values masked</span>
              </div>

              {visibleItems.length ? (
                <div className="client-entity-list">
                  {visibleItems.map((item) => (
                    <div className="client-entity-row" key={item.key}>
                      <div>
                        <span>{item.label}</span>
                        <strong>{item.maskedValue}</strong>
                      </div>
                      <small>
                        {item.occurrences} occurrence
                        {item.occurrences === 1 ? "" : "s"}
                      </small>
                    </div>
                  ))}

                  {detectedItems.length > 10 ? (
                    <button
                      type="button"
                      className="client-show-more no-print"
                      onClick={() => setShowAllItems((current) => !current)}
                    >
                      {showAllItems
                        ? "Show fewer items"
                        : `Show all ${detectedItems.length} items`}
                    </button>
                  ) : null}
                </div>
              ) : (
                <p className="client-empty-copy">
                  No sensitive items were returned by this analysis.
                </p>
              )}
            </div>
          </section>

          <section className="client-review-note">
            <strong>Human review remains part of the workflow.</strong>
            <span>
              This summary describes what the detector found. It does not claim
              that undetected sensitive data is absent from the document.
            </span>
          </section>

          <footer className="client-report-footer">
            <span>Read-only client output preview</span>
            <span>Raw sensitive values are masked in the summary.</span>
          </footer>
        </div>
      </article>

      <section className="experiment-truth-panel">
        <div className="experiment-truth-panel__header">
          <div>
            <span className="kicker">Experiments only · hidden from client</span>
            <h3>Benchmark validation of this client-facing result</h3>
            <p>
              This panel compares the polished client output above with the
              labeled ground truth, so we can detect a dangerous “looks safe”
              UX when the model actually missed PII.
            </p>
          </div>
          <button
            type="button"
            className="experiment-truth-toggle"
            onClick={() => setShowBenchmarkTruth((current) => !current)}
          >
            {showBenchmarkTruth ? "Hide validation" : "Show validation"}
          </button>
        </div>

        {showBenchmarkTruth ? (
          <>
            <div className="experiment-truth-metrics">
              <ClientMetric
                label="Recall"
                value={formatPercent(benchmark.recall)}
                hint="Gold PII detected"
              />
              <ClientMetric
                label="Leakage"
                value={formatPercent(benchmark.leakage)}
                hint="Gold PII chars left exposed"
              />
              <ClientMetric
                label="Precision"
                value={formatPercent(benchmark.precision)}
                hint="Resolved findings accuracy"
              />
              <ClientMetric
                label="Missed gold spans"
                value={benchmark.missed}
                hint={`of ${benchmark.gold} annotated spans`}
              />
            </div>

            <div className="experiment-truth-details">
              <div>
                <strong>What the client preview hides</strong>
                <p>
                  {benchmark.missed > 0
                    ? `The polished output above looks complete, but the benchmark knows ${benchmark.missed} annotated PII span${benchmark.missed === 1 ? " was" : "s were"} missed.`
                    : "No labeled PII spans were missed for this document/model evidence."}
                </p>
              </div>
              <div>
                <strong>Over-redaction</strong>
                <p>
                  {benchmark.overRedacted > 0
                    ? `${benchmark.overRedacted} resolved prediction${benchmark.overRedacted === 1 ? " does" : "s do"} not match the gold annotations.`
                    : "No unmatched resolved predictions are recorded for this evidence."}
                </p>
              </div>
              {!modelData?.valid ? (
                <div className="experiment-truth-error">
                  <strong>Inference failure</strong>
                  <p>{modelData?.error ?? modelData?.status ?? "Unknown inference failure"}</p>
                </div>
              ) : null}
            </div>

            {(modelData?.missed ?? []).length ? (
              <details className="experiment-missed-details">
                <summary>
                  Inspect missed spans ({modelData.missed.length}) — benchmark only
                </summary>
                <div>
                  {modelData.missed.slice(0, 30).map((span, index) => (
                    <span key={`${span.start}-${span.end}-${index}`}>
                      <b>{labelForType(span.pii_type)}</b>
                      <code>{span.value}</code>
                    </span>
                  ))}
                </div>
              </details>
            ) : null}
          </>
        ) : null}
      </section>
    </div>
  );
}

export default ClientOutputPreview;
