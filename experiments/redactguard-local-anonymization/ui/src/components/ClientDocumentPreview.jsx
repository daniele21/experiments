import { useMemo, useState } from "react";

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

function validSpans(text, spans, status) {
  const seen = new Set();
  return (spans ?? [])
    .map((span, index) => ({
      ...span,
      status,
      index,
      start: Number(span.start),
      end: Number(span.end),
    }))
    .filter((span) => (
      Number.isInteger(span.start) &&
      Number.isInteger(span.end) &&
      span.start >= 0 &&
      span.end > span.start &&
      span.end <= text.length
    ))
    .filter((span) => {
      const key = `${span.start}:${span.end}:${span.pii_type}:${status}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function buildCoverageSegments(text, detected, missed) {
  const all = [
    ...validSpans(text, detected, "detected"),
    ...validSpans(text, missed, "missed"),
  ].sort((left, right) => {
    if (left.start !== right.start) return left.start - right.start;
    if (left.status !== right.status) {
      // Missed PII wins an overlap visually because it represents exposed risk.
      return left.status === "missed" ? -1 : 1;
    }
    return right.end - left.end;
  });

  const segments = [];
  let cursor = 0;

  for (const span of all) {
    if (span.start < cursor) continue;

    if (span.start > cursor) {
      segments.push({
        kind: "text",
        key: `text-${cursor}-${span.start}`,
        text: text.slice(cursor, span.start),
      });
    }

    segments.push({
      kind: "pii",
      key: `${span.status}-${span.start}-${span.end}-${span.pii_type}-${span.index}`,
      text: text.slice(span.start, span.end),
      piiType: span.pii_type,
      label: typeLabel(span.pii_type),
      start: span.start,
      end: span.end,
      status: span.status,
    });
    cursor = span.end;
  }

  if (cursor < text.length) {
    segments.push({
      kind: "text",
      key: `text-${cursor}-end`,
      text: text.slice(cursor),
    });
  }

  return segments;
}

function categorySummary(findings) {
  const counts = new Map();
  for (const finding of findings ?? []) {
    const current = counts.get(finding.pii_type) ?? 0;
    counts.set(finding.pii_type, current + 1);
  }
  return [...counts.entries()]
    .map(([type, count]) => ({
      type,
      label: typeLabel(type),
      count,
    }))
    .sort(
      (left, right) =>
        right.count - left.count || left.label.localeCompare(right.label),
    );
}

export function ClientDocumentPreview({
  documentData,
  model,
}) {
  const [mode, setMode] = useState("coverage");
  const [revealedDetected, setRevealedDetected] = useState(new Set());

  const text = documentData?.text ?? "";
  const modelData = documentData?.models?.[model] ?? null;
  const findings = modelData?.redactions ?? [];
  const missed = modelData?.missed ?? [];

  const segments = useMemo(
    () => buildCoverageSegments(text, findings, missed),
    [text, findings, missed],
  );

  const detectedCategories = useMemo(
    () => categorySummary(findings),
    [findings],
  );

  const missedCategories = useMemo(
    () => categorySummary(missed),
    [missed],
  );

  const toggleReveal = (segmentKey) => {
    setRevealedDetected((current) => {
      const next = new Set(current);
      if (next.has(segmentKey)) next.delete(segmentKey);
      else next.add(segmentKey);
      return next;
    });
  };

  const revealAllDetected = () => {
    setRevealedDetected(
      new Set(
        segments
          .filter((segment) => segment.kind === "pii" && segment.status === "detected")
          .map((segment) => segment.key),
      ),
    );
  };

  const hideAllDetected = () => {
    setRevealedDetected(new Set());
  };

  if (modelData && modelData.valid === false) {
    return (
      <section className="client-document-preview client-document-preview--unavailable">
        <div>
          <span className="client-journey-kicker">Document preview</span>
          <h3>Preview unavailable</h3>
          <p>
            This model did not produce a valid inference for the selected document,
            so a “0 PII” preview would be misleading.
          </p>
        </div>
      </section>
    );
  }

  if (!text) {
    return (
      <section className="client-document-preview client-document-preview--empty">
        <div>
          <span className="client-journey-kicker">Document preview</span>
          <h3>Preview unavailable</h3>
          <p>The canonical document text is not available for this evidence.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="client-document-preview">
      <header className="client-document-preview__header">
        <div>
          <span className="client-journey-kicker">Document preview</span>
          <h3>PII coverage in context</h3>
          <p>
            See what <strong>{model}</strong> identified and what the benchmark
            says it missed in the same source document.
          </p>
        </div>

        <div
          className="client-document-preview__mode"
          role="radiogroup"
          aria-label="Document preview mode"
        >
          <button
            type="button"
            className={mode === "coverage" ? "active" : ""}
            onClick={() => setMode("coverage")}
            role="radio"
            aria-checked={mode === "coverage"}
          >
            Coverage
          </button>
          <button
            type="button"
            className={mode === "redacted" ? "active" : ""}
            onClick={() => setMode("redacted")}
            role="radio"
            aria-checked={mode === "redacted"}
          >
            Redacted
          </button>
        </div>
      </header>

      <div className="client-document-preview__summary client-document-preview__summary--coverage">
        <div className="client-document-preview__coverage-stat">
          <span className="client-coverage-dot client-coverage-dot--detected" />
          <div>
            <strong>{findings.length}</strong>
            <span>PII identified</span>
          </div>
        </div>

        <div className="client-document-preview__coverage-stat client-document-preview__coverage-stat--missed">
          <span className="client-coverage-dot client-coverage-dot--missed" />
          <div>
            <strong>{missed.length}</strong>
            <span>PII missed / exposed</span>
          </div>
        </div>

        <div className="client-document-preview__legend">
          <span className="client-document-preview__legend-status client-document-preview__legend-status--detected">
            <i />
            Detected by model
          </span>
          <span className="client-document-preview__legend-status client-document-preview__legend-status--missed">
            <i />
            Missed by model
          </span>
        </div>
      </div>

      {mode === "redacted" ? (
        <div className="client-document-preview__reveal-bar">
          <span>
            Click any redacted PII to reveal what the model masked.
          </span>
          <div>
            <button type="button" onClick={revealAllDetected}>
              Reveal all detected
            </button>
            <button type="button" onClick={hideAllDetected}>
              Hide all detected
            </button>
          </div>
        </div>
      ) : null}

      <div
        className="client-document-preview__canvas"
        aria-label="Document text with detected and missed PII"
      >
        <div className="client-document-preview__paper">
          {segments.map((segment) => {
            if (segment.kind === "text") {
              return <span key={segment.key}>{segment.text}</span>;
            }

            if (segment.status === "missed") {
              return (
                <mark
                  key={segment.key}
                  className="client-pii-missed"
                  title={`Missed ${segment.label} · chars ${segment.start}–${segment.end}`}
                >
                  {segment.text}
                  <span className="client-pii-missed__label">
                    MISSED · {segment.label}
                  </span>
                </mark>
              );
            }

            if (mode === "redacted") {
              const isRevealed = revealedDetected.has(segment.key);
              return (
                <button
                  key={segment.key}
                  type="button"
                  className={`client-pii-redaction client-pii-redaction--interactive ${
                    isRevealed ? "client-pii-redaction--revealed" : ""
                  }`}
                  onClick={() => toggleReveal(segment.key)}
                  title={
                    isRevealed
                      ? `Hide ${segment.label}`
                      : `Reveal ${segment.label}`
                  }
                >
                  {isRevealed
                    ? segment.text
                    : `[REDACTED ${segment.label.toUpperCase()}]`}
                  <span className="client-pii-redaction__hint">
                    {isRevealed ? "hide" : "reveal"}
                  </span>
                </button>
              );
            }

            return (
              <mark
                key={segment.key}
                className="client-pii-highlight"
                title={`Detected ${segment.label} · chars ${segment.start}–${segment.end}`}
              >
                {segment.text}
                <span className="client-pii-highlight__label">
                  DETECTED · {segment.label}
                </span>
              </mark>
            );
          })}
        </div>
      </div>

      <div className="client-document-preview__categories">
        <details>
          <summary>Detected categories ({detectedCategories.length})</summary>
          <div>
            {detectedCategories.map((category) => (
              <span key={category.type}>
                {category.label} <b>{category.count}</b>
              </span>
            ))}
            {!detectedCategories.length ? <span>None</span> : null}
          </div>
        </details>

        <details>
          <summary>Missed categories ({missedCategories.length})</summary>
          <div>
            {missedCategories.map((category) => (
              <span key={category.type}>
                {category.label} <b>{category.count}</b>
              </span>
            ))}
            {!missedCategories.length ? <span>None</span> : null}
          </div>
        </details>
      </div>

      <footer className="client-document-preview__footer">
        <span>
          Detected PII represents what the model would protect. Missed PII comes
          from the benchmark ground truth and remains exposed in the redacted view.
        </span>
      </footer>
    </section>
  );
}

export default ClientDocumentPreview;
