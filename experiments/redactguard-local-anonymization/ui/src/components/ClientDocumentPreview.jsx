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

function validSpans(text, findings) {
  const seen = new Set();
  return (findings ?? [])
    .filter((span) => {
      const start = Number(span.start);
      const end = Number(span.end);
      return (
        Number.isInteger(start) &&
        Number.isInteger(end) &&
        start >= 0 &&
        end > start &&
        end <= text.length
      );
    })
    .sort((left, right) => {
      if (left.start !== right.start) return left.start - right.start;
      return right.end - left.end;
    })
    .filter((span) => {
      const key = `${span.start}:${span.end}:${span.pii_type}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function buildSegments(text, findings) {
  const spans = validSpans(text, findings);
  const segments = [];
  let cursor = 0;

  spans.forEach((span, index) => {
    if (span.start < cursor) return;

    if (span.start > cursor) {
      segments.push({
        kind: "text",
        key: `text-${cursor}-${span.start}`,
        text: text.slice(cursor, span.start),
      });
    }

    segments.push({
      kind: "pii",
      key: `pii-${span.start}-${span.end}-${span.pii_type}-${index}`,
      text: text.slice(span.start, span.end),
      piiType: span.pii_type,
      label: typeLabel(span.pii_type),
      start: span.start,
      end: span.end,
    });
    cursor = span.end;
  });

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
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

export function ClientDocumentPreview({
  documentData,
  model,
}) {
  const [mode, setMode] = useState("highlighted");
  const text = documentData?.text ?? "";
  const findings = documentData?.models?.[model]?.redactions ?? [];

  const segments = useMemo(
    () => buildSegments(text, findings),
    [text, findings],
  );
  const categories = useMemo(
    () => categorySummary(findings),
    [findings],
  );

  if (!text) {
    return (
      <section className="client-document-preview client-document-preview--empty">
        <div>
          <span>Document preview</span>
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
          <h3>PII identified in context</h3>
          <p>
            The highlighted spans are the sensitive values identified by{" "}
            <strong>{model}</strong> in this document.
          </p>
        </div>

        <div className="client-document-preview__mode" role="radiogroup" aria-label="Document preview mode">
          <button
            type="button"
            className={mode === "highlighted" ? "active" : ""}
            onClick={() => setMode("highlighted")}
            role="radio"
            aria-checked={mode === "highlighted"}
          >
            Highlighted
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

      <div className="client-document-preview__summary">
        <div className="client-document-preview__count">
          <strong>{findings.length}</strong>
          <span>PII occurrences identified</span>
        </div>
        <div className="client-document-preview__legend">
          {categories.map((category) => (
            <span key={category.type}>
              <i className={`client-pii-dot client-pii-dot--${category.type}`} />
              {category.label}
              <b>{category.count}</b>
            </span>
          ))}
          {!categories.length ? (
            <span className="client-document-preview__none">No PII identified</span>
          ) : null}
        </div>
      </div>

      <div className="client-document-preview__canvas" aria-label="Document text with identified PII">
        <div className="client-document-preview__paper">
          {segments.map((segment) => {
            if (segment.kind === "text") {
              return <span key={segment.key}>{segment.text}</span>;
            }

            if (mode === "redacted") {
              return (
                <span
                  key={segment.key}
                  className="client-pii-redaction"
                  title={segment.label}
                >
                  [REDACTED {segment.label.toUpperCase()}]
                </span>
              );
            }

            return (
              <mark
                key={segment.key}
                className={`client-pii-highlight client-pii-highlight--${segment.piiType}`}
                title={`${segment.label} · chars ${segment.start}–${segment.end}`}
              >
                {segment.text}
                <span className="client-pii-highlight__label">{segment.label}</span>
              </mark>
            );
          })}
        </div>
      </div>

      <footer className="client-document-preview__footer">
        <span>
          This preview shows model detections only. Benchmark misses and extra detections
          remain in the evidence sections below.
        </span>
      </footer>
    </section>
  );
}

export default ClientDocumentPreview;
