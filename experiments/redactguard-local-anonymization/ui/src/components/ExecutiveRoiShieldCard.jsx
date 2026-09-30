/**
 * ExecutiveRoiShieldCard.jsx
 *
 * Executive TCO & Privacy Shield widget comparing local open-weight model deployment
 * against commercial third-party cloud APIs (e.g. OpenAI / Anthropic).
 * Demonstrates GDPR sovereignty, zero exfiltration, and tangible operational cost savings.
 */

import { useState } from "react";
import { uiConfig } from "../config/uiConfig";

export function ExecutiveRoiShieldCard({ recommendedModel }) {
  const config = uiConfig.executive?.roiEstimator ?? {
    defaultDocsPerMonth: 5000,
    avgTokensPerDoc: 2500,
    cloudCostPerMillionTokens: 4.5,
    localHostingMonthlyEstimate: 160,
  };

  const [docsPerMonth, setDocsPerMonth] = useState(config.defaultDocsPerMonth);

  // Computations
  const totalTokensMonthly = docsPerMonth * config.avgTokensPerDoc;
  const cloudCostMonthly = Math.round(
    (totalTokensMonthly / 1_000_000) * config.cloudCostPerMillionTokens,
  );
  const cloudCostAnnual = cloudCostMonthly * 12;

  const localCostMonthly = config.localHostingMonthlyEstimate;
  const localCostAnnual = localCostMonthly * 12;

  const annualSavings = Math.max(0, cloudCostAnnual - localCostAnnual);
  const savingsPercent =
    cloudCostAnnual > 0 ? Math.round((annualSavings / cloudCostAnnual) * 100) : 0;

  return (
    <div className="executive-roi-card">
      <div className="panel-heading">
        <div>
          <span className="kicker">Business Case & TCO</span>
          <h2>Privacy Shield & Ritorno sull'Investimento (ROI)</h2>
        </div>
        <span className="panel-note">
          Confronto tra elaborazione locale {recommendedModel ? `(${recommendedModel.model})` : ""} e API Cloud commerciali
        </span>
      </div>

      <div className="roi-card-layout">
        {/* Left Column: Privacy Shield & Compliance Sovereign Guarantees */}
        <div className="roi-shield-column">
          <div className="shield-hero-badge">
            <span className="shield-icon">🛡️</span>
            <div>
              <strong>Garanzia Sovranità & Privacy Shield</strong>
              <small>Zero fughe all'esterno del perimetro aziendale</small>
            </div>
          </div>

          <div className="shield-points-list">
            <div className="shield-point">
              <span className="point-icon">🔒</span>
              <div>
                <strong>Zero Data Exfiltration (Elaborazione 100% Locale)</strong>
                <p>
                  I documenti bancari, sanitari e contrattuali vengono elaborati in locale. Nessun dato lascia mai i vostri server verso provider cloud esterni.
                </p>
              </div>
            </div>

            <div className="shield-point">
              <span className="point-icon">⚖️</span>
              <div>
                <strong>Conformità GDPR & Immunità da US Cloud Act</strong>
                <p>
                  Nessun trasferimento transfrontaliero di dati (Schrems II). Esclusione immediata dal rischio di sanzioni per esportazione indebita di dati riservati.
                </p>
              </div>
            </div>

            <div className="shield-point">
              <span className="point-icon">🔓</span>
              <div>
                <strong>Zero Vendor Lock-in & Indipendenza da API Esterne</strong>
                <p>
                  Modelli con pesi aperti di proprietà aziendale: nessuna dipendenza da aumenti tariffari improvvisi, dismissioni di modelli o downtime di terze parti.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Interactive TCO Savings Calculator */}
        <div className="roi-calculator-column">
          <div className="calculator-header">
            <strong>Calcolatore del Risparmio Operativo</strong>
            <small>Stima TCO su base annua</small>
          </div>

          {/* Volume Slider */}
          <div className="roi-slider-group">
            <div className="roi-slider-labels">
              <span>Volume Documentale Mensile:</span>
              <strong>{docsPerMonth.toLocaleString("it-IT")} documenti/mese</strong>
            </div>
            <input
              type="range"
              min="1000"
              max="30000"
              step="1000"
              value={docsPerMonth}
              onChange={(e) => setDocsPerMonth(Number(e.target.value))}
              className="roi-slider-input"
            />
            <div className="roi-slider-scale">
              <span>1k</span>
              <span>10k</span>
              <span>20k</span>
              <span>30k doc/mese</span>
            </div>
          </div>

          {/* Cost Comparison Metric Tiles */}
          <div className="roi-metrics-grid">
            <div className="roi-cost-tile roi-cost-tile--cloud">
              <span className="cost-tile-label">Costo Annuo API Cloud</span>
              <strong className="cost-tile-amount">
                € {cloudCostAnnual.toLocaleString("it-IT")}
              </strong>
              <small>€ {cloudCostMonthly.toLocaleString("it-IT")} / mese (GPT-4o/Claude)</small>
            </div>

            <div className="roi-cost-tile roi-cost-tile--local">
              <span className="cost-tile-label">Costo Annuo Locale</span>
              <strong className="cost-tile-amount">
                € {localCostAnnual.toLocaleString("it-IT")}
              </strong>
              <small>€ {localCostMonthly.toLocaleString("it-IT")} / mese (Server/GPU fisso)</small>
            </div>
          </div>

          {/* Net Savings Callout */}
          <div className="roi-savings-banner">
            <div className="savings-badge">
              <span>RISPARMIO NETTO STIMATO</span>
            </div>
            <div className="savings-row">
              <strong className="savings-amount">
                € {annualSavings.toLocaleString("it-IT")}
                <span className="savings-freq"> / anno</span>
              </strong>
              <span className="savings-percent-tag">-{savingsPercent}% Costi</span>
            </div>
            <p className="savings-subtext">
              L'infrastruttura locale si ammortizza completamente in meno di <strong>3 mesi</strong> di operatività standard.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExecutiveRoiShieldCard;
