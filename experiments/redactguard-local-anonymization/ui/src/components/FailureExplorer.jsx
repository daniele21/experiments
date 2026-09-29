import { uiConfig } from "../config/uiConfig";
import { formatPercent } from "../utils/formatters";

/**
 * Interactive list of false negatives, false positives, and system errors
 * for diagnostic inspection per model.
 */
export function FailureExplorer({
  failures = [],
  selectedModel = null,
  models = [],
  allFailures = {},
  onSelectModel = null,
}) {
  const { maxVisibleCases, maxVisibleSpans } = uiConfig.failureExplorer;

  return (
    <div className="failure-explorer-container">
      {/* Quick model switch bar within the diagnostics section */}
      {models?.length > 1 && onSelectModel && (
        <div className="failure-model-selector" role="tablist" aria-label="Filtra per modello">
          <span className="failure-model-selector__label">Modello:</span>
          {models.map((model) => {
            const count = allFailures?.[model]?.length ?? 0;
            const isSelected = model === selectedModel;
            return (
              <button
                key={model}
                type="button"
                role="tab"
                aria-selected={isSelected}
                className={`failure-model-btn ${isSelected ? "active" : ""}`}
                onClick={() => onSelectModel(model)}
              >
                <span className="failure-model-btn__name">{model}</span>
                <span
                  className={`failure-count-badge ${
                    count > 0 ? "failure-count-badge--alert" : "failure-count-badge--clean"
                  }`}
                >
                  {count === 0 ? "✓ 0" : count}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Model banner */}
      {selectedModel && (
        <div className="failure-active-banner">
          <span>
            Diagnostica per <strong>{selectedModel}</strong>
          </span>
          <span className="panel-note">
            {failures.length === 0
              ? "0 anomalie riscontrate"
              : `${failures.length} caso/i con anomalie o errori`}
          </span>
        </div>
      )}

      {/* Empty State when no failures exist for this model */}
      {!failures?.length ? (
        <div className="empty-state failure-empty-state">
          <div className="failure-empty-state__icon">✓</div>
          <strong>Nessuna failure per {selectedModel ?? "questo modello"}</strong>
          <span>
            Tutti i documenti valutati hanno superato l'inferenza senza errori di sintassi né
            violazioni critiche di policy in questo run.
          </span>
        </div>
      ) : (
        <div className="failure-list">
          {failures.slice(0, maxVisibleCases).map((failure, index) => (
            <details key={`${failure.case_id ?? "case"}-${index}`} open={index === 0}>
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
                  <span className="eyebrow">Missed gold spans (FN)</span>
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
                  <span className="eyebrow">Unmatched predictions (FP)</span>
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
      )}
    </div>
  );
}

export default FailureExplorer;
