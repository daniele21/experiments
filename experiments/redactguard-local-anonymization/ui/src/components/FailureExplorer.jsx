import { uiConfig } from "../config/uiConfig";
import { formatPercent } from "../utils/formatters";

/**
 * Interactive list of false negatives and false positives for diagnostic inspection.
 */
export function FailureExplorer({ failures }) {
  if (!failures?.length) {
    return (
      <div className="empty-state">
        <strong>No recorded failures</strong>
        <span>This model has no cases in the failure analysis for the selected run.</span>
      </div>
    );
  }

  const { maxVisibleCases, maxVisibleSpans } = uiConfig.failureExplorer;

  return (
    <div className="failure-list">
      {failures.slice(0, maxVisibleCases).map((failure, index) => (
        <details key={`${failure.case_id ?? "case"}-${index}`}>
          <summary>
            <span>
              <strong>{failure.case_id ?? "Unknown case"}</strong>
              <small>
                Recall {formatPercent(failure.pii_recall)} · Leakage{" "}
                {formatPercent(failure.leakage_rate)}
              </small>
            </span>
            <span className="failure-counts">
              FN {failure.fn ?? 0} · FP {failure.fp ?? 0}
            </span>
          </summary>
          <div className="failure-body">
            <div>
              <span className="eyebrow">Missed gold spans</span>
              {(failure.false_negatives ?? []).length ? (
                <ul>
                  {failure.false_negatives.slice(0, maxVisibleSpans).map((item, itemIndex) => (
                    <li key={itemIndex}>
                      <code>{item.pii_type ?? "PII"}</code> {item.value ?? ""}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">None</p>
              )}
            </div>
            <div>
              <span className="eyebrow">Unmatched predictions</span>
              {(failure.false_positives ?? []).length ? (
                <ul>
                  {failure.false_positives.slice(0, maxVisibleSpans).map((item, itemIndex) => (
                    <li key={itemIndex}>
                      <code>{item.pii_type ?? "PII"}</code> {item.value ?? ""}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">None</p>
              )}
            </div>
          </div>
          {failure.error ? <p className="error-inline">{failure.error}</p> : null}
        </details>
      ))}
    </div>
  );
}

export default FailureExplorer;
