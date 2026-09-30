/**
 * ExecutiveDecisionTable.jsx
 *
 * Executive decision table distilling candidate models into actionable governance,
 * privacy protection, reliability, and deployment recommendations.
 */

import { formatMs, formatPercent } from "../utils/formatters";
import { MiniBar } from "./MetricCard";

export function ExecutiveDecisionTable({
  models = [],
  recommendedModel,
  selectedModel,
  onSelectModel,
  onNavigateToDocuments,
}) {
  return (
    <div className="executive-table-card">
      <div className="panel-heading">
        <div>
          <span className="kicker">Graduatoria Comparativa</span>
          <h2>Matrice di Decisione per il Deployment</h2>
        </div>
        <span className="panel-note">
          Valutazione di idoneità basata su standard GDPR e conformità operativa
        </span>
      </div>

      <div className="table-scroll">
        <table className="executive-table">
          <thead>
            <tr>
              <th>Modello Candidato</th>
              <th>Stato Contratto</th>
              <th>Protezione Privacy (Recall)</th>
              <th>Zero-Leak Documenti</th>
              <th>Rischio Residuo Leakage</th>
              <th>Affidabilità Esecuzione</th>
              <th>Latenza (p95)</th>
              <th>Verdetto Esecutivo</th>
              {onNavigateToDocuments && <th className="no-print">Evidenze</th>}
            </tr>
          </thead>
          <tbody>
            {models.map((item) => {
              const isRecommended = item.model === recommendedModel?.model;
              const isSelected = item.model === selectedModel;

              return (
                <tr
                  key={item.model}
                  className={`executive-table-row ${
                    isRecommended ? "executive-table-row--recommended" : ""
                  } ${isSelected ? "executive-table-row--selected" : ""}`}
                  onClick={() => onSelectModel?.(item.model)}
                >
                  <td className="model-name-cell">
                    <div className="executive-model-title">
                      <strong>{item.model}</strong>
                      {isRecommended && (
                        <span className="executive-rec-badge">
                          ⭐ Scelta Consigliata
                        </span>
                      )}
                    </div>
                  </td>

                  <td>
                    <span
                      className={`status-badge ${
                        item.state === "passed"
                          ? "status-badge--passed"
                          : item.state === "failed"
                            ? "status-badge--failed"
                            : "status-badge--legacy"
                      }`}
                    >
                      {item.state === "passed"
                        ? "v3 verificato"
                        : item.state === "failed"
                          ? "fallito"
                          : "legacy"}
                    </span>
                  </td>

                  <td>
                    <div className="table-metric-bar-group">
                      <span className="table-metric-val">
                        {formatPercent(item.recall)}
                      </span>
                      <MiniBar value={item.recall} />
                    </div>
                  </td>

                  <td>
                    <div className="table-metric-bar-group">
                      <span className="table-metric-val">
                        {formatPercent(item.zeroLeakDocs)}
                      </span>
                      <MiniBar value={item.zeroLeakDocs} />
                    </div>
                  </td>

                  <td>
                    <div className="table-leakage-group">
                      <span
                        className={`table-leakage-val ${
                          item.leakage > 0.1 ? "table-leakage-val--high" : ""
                        }`}
                      >
                        {formatPercent(item.leakage)}
                      </span>
                      {item.systemLeakage > item.leakage + 0.1 && (
                        <small
                          className="table-system-leakage-warning"
                          title="Fuga di dati a livello di sistema dovuta a timeout o crash"
                        >
                          ⚠️ {formatPercent(item.systemLeakage)} effettivo
                        </small>
                      )}
                    </div>
                  </td>

                  <td>
                    <div className="table-reliability-cell">
                      <strong
                        className={
                          item.successRate >= 0.95
                            ? "text-positive"
                            : "text-risk"
                        }
                      >
                        {formatPercent(item.successRate)}
                      </strong>
                      {item.errorSummary && (
                        <small className="table-error-hint" title={item.errorSummary}>
                          {item.errorSummary}
                        </small>
                      )}
                    </div>
                  </td>

                  <td>
                    <span className="table-latency-val">
                      {formatMs(item.latencyP95)}
                    </span>
                  </td>

                  <td>
                    <span
                      className={`executive-verdict-pill executive-verdict-pill--${item.tone}`}
                    >
                      {item.badge}
                    </span>
                  </td>

                  {onNavigateToDocuments && (
                    <td className="table-actions-cell no-print">
                      <button
                        type="button"
                        className="btn-table-audit"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectModel?.(item.model);
                          onNavigateToDocuments?.();
                        }}
                        title={`Esamina le prove per ${item.model} nel visualizzatore documenti`}
                      >
                        Audit ↗
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ExecutiveDecisionTable;
