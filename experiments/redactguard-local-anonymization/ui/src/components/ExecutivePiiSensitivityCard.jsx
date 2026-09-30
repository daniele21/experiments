/**
 * ExecutivePiiSensitivityCard.jsx
 *
 * Executive view breakdown displaying protection coverage across GDPR PII sensitivity
 * categories (Email, Phone, Person Names, IBAN, Addresses) and business domains (Legal vs Financial).
 */

import { formatPercent } from "../utils/formatters";
import { MiniBar } from "./MetricCard";

export function ExecutivePiiSensitivityCard({
  piiBreakdown = [],
  profileBreakdown = [],
  modelName,
}) {
  if (!piiBreakdown.length && !profileBreakdown.length) {
    return null;
  }

  return (
    <div className="executive-sensitivity-container">
      {/* PII Types Breakdown */}
      <div className="executive-pii-card">
        <div className="panel-heading">
          <div>
            <span className="kicker">Analisi di Sensibilità GDPR</span>
            <h3>Protezione per Tipologia di Dato Sensibile</h3>
          </div>
          <span className="panel-note">{modelName}</span>
        </div>

        <div className="executive-pii-grid">
          {piiBreakdown.map((item) => {
            const isZeroLeak = item.recall >= 0.99;
            const isHigh = item.recall >= 0.9;
            const statusClass = isZeroLeak
              ? "pii-tag--zero-leak"
              : isHigh
                ? "pii-tag--high"
                : "pii-tag--attention";

            return (
              <div key={item.type} className="executive-pii-item">
                <div className="pii-item-header">
                  <div className="pii-item-title">
                    <span className="pii-icon">{item.icon}</span>
                    <div>
                      <strong>{item.label}</strong>
                      <small>
                        {item.tp} oscurati / {item.goldCount} totali
                        {item.fn > 0 ? ` (${item.fn} non oscurati)` : ""}
                      </small>
                    </div>
                  </div>
                  <span className={`pii-status-pill ${statusClass}`}>
                    {isZeroLeak ? "✓ 100% Zero-Leak" : `${formatPercent(item.recall)}`}
                  </span>
                </div>
                <div className="pii-item-bar">
                  <MiniBar value={item.recall} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Business Domains Breakdown */}
      {profileBreakdown.length > 0 && (
        <div className="executive-profile-card">
          <div className="panel-heading">
            <div>
              <span className="kicker">Idoneità per Dipartimento</span>
              <h3>Copertura per Ambito Aziendale</h3>
            </div>
          </div>

          <div className="executive-profile-list">
            {profileBreakdown.map((prof) => (
              <div key={prof.profile} className="executive-profile-item">
                <div className="profile-item-header">
                  <span className="profile-icon">{prof.icon}</span>
                  <div className="profile-text">
                    <strong>{prof.label}</strong>
                    <p>{prof.desc}</p>
                  </div>
                  <div className="profile-metric">
                    <strong>{formatPercent(prof.recall)}</strong>
                    <small>{prof.cases} documenti</small>
                  </div>
                </div>
                <div className="profile-item-bar">
                  <MiniBar value={prof.recall} />
                </div>
              </div>
            ))}
          </div>

          <div className="profile-takeaway-note">
            <span>💡</span>
            <p>
              I contratti legali raggiungono una conformità pressoché totale (<strong>98.5%+</strong>).
              I report finanziari e contabili beneficiano di un processo Human-in-the-Loop per gli IBAN e conti correnti.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default ExecutivePiiSensitivityCard;
