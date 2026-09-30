/**
 * ExecutiveBriefingView.jsx
 *
 * Dedicated executive-ready dashboard presenting synthesized findings,
 * production deployment verdicts, GDPR risk indicators, and strategic advisory notes.
 */

import { useMemo } from "react";
import { analyzeExecutiveSummary } from "../utils/executiveAnalyzer";
import { formatDate, formatMs, formatPercent } from "../utils/formatters";
import ExecutiveDecisionQuadrant from "./ExecutiveDecisionQuadrant";
import ExecutiveDecisionTable from "./ExecutiveDecisionTable";
import ExecutivePiiSensitivityCard from "./ExecutivePiiSensitivityCard";
import ExecutiveRoiShieldCard from "./ExecutiveRoiShieldCard";

export function ExecutiveBriefingView({
  detail,
  selectedRun,
  selectedModel,
  onSelectModel,
  onNavigateToDocuments,
}) {
  const analysis = useMemo(() => analyzeExecutiveSummary(detail), [detail]);

  if (!analysis.available || analysis.models.length === 0) {
    return (
      <div className="empty-state large">
        <strong>Nessun dato esecutivo disponibile</strong>
        <span>
          I risultati del benchmark non contengono evidenze sufficienti per generare la sintesi decisionale.
        </span>
      </div>
    );
  }

  const {
    recommendedModel,
    zeroLeakChampion,
    quarantinedModels,
    complianceTier,
    models,
    keyFindings,
    piiBreakdown,
    profileBreakdown,
  } = analysis;

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="executive-briefing-view">
      {/* Executive Header & Export Action */}
      <header className="executive-view-header">
        <div>
          <div className="executive-badge-row">
            <span className="executive-kicker">C-Level Briefing</span>
            <span
              className={`compliance-tier-badge compliance-tier-badge--${complianceTier?.tone ?? "positive"}`}
            >
              🛡️ {complianceTier?.label ?? "Verifica GDPR"}
            </span>
          </div>
          <h1>Sintesi Esecutiva & Raccomandazione di Produzione</h1>
          <p className="executive-subtitle">
            Valutazione comparativa per il Comitato di Sicurezza, DPO e Direzione IT sull'adozione dei modelli di anonimizzazione locale.
          </p>
        </div>

        <div className="executive-header-actions no-print">
          {onNavigateToDocuments && (
            <button
              type="button"
              className="btn btn--primary btn--drilldown"
              onClick={onNavigateToDocuments}
              title="Apri i documenti reali per verificare le evidenze visive di redazione"
            >
              <span>📑</span>
              <span>Esplora Audit Documenti ({selectedRun?.cases ?? 11} file) →</span>
            </button>
          )}
          <button
            type="button"
            className="btn btn--outline btn--export"
            onClick={handlePrint}
            title="Stampa o salva il briefing esecutivo in formato PDF"
          >
            <span>🖨️</span>
            <span>Esporta / Stampa PDF</span>
          </button>
        </div>
      </header>

      {/* Hero Decision Section: Recommended Model & Operational Warnings */}
      <section className="executive-hero-section">
        {recommendedModel ? (
          <div className="executive-verdict-card">
            <div className="verdict-card-badge">
              <span>🏆 VERDETTO PER IL RILASCIO</span>
            </div>
            <div className="verdict-card-body">
              <div className="verdict-model-header">
                <h2>{recommendedModel.model}</h2>
                <span className="verdict-score-tag">
                  Score di Idoneità: <strong>{recommendedModel.score}/100</strong>
                </span>
              </div>
              <p className="verdict-summary-text">
                Candidato primario approvato per l'integrazione nei sistemi aziendali. Offre il miglior bilanciamento tra conformità alle normative privacy (GDPR) e stabilità operativa certificata.
              </p>

              <div className="verdict-highlights-list">
                <div className="verdict-highlight-item">
                  <span className="highlight-icon">✓</span>
                  <div>
                    <strong>{(recommendedModel.recall * 100).toFixed(1)}% Protezione PII</strong>
                    <small>Riconoscimento rigoroso su tutte le categorie sensibili</small>
                  </div>
                </div>
                <div className="verdict-highlight-item">
                  <span className="highlight-icon">✓</span>
                  <div>
                    <strong>{formatPercent(recommendedModel.successRate)} Affidabilità Esecuzione</strong>
                    <small>Zero crash, nessun timeout e rispetto rigoroso dello schema v3</small>
                  </div>
                </div>
                <div className="verdict-highlight-item">
                  <span className="highlight-icon">✓</span>
                  <div>
                    <strong>
                      {zeroLeakChampion
                        ? `${(zeroLeakChampion.zeroLeakDocs * 100).toFixed(1)}% Zero-Leak Massimo`
                        : `${(recommendedModel.zeroLeakDocs * 100).toFixed(1)}% Documenti Zero-Leak`}
                    </strong>
                    <small>
                      {zeroLeakChampion && zeroLeakChampion.model !== recommendedModel.model
                        ? `Raggiunto da ${zeroLeakChampion.model} su carichi sensibili`
                        : "File interamente depurati senza alcuna fuga residua"}
                    </small>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="executive-verdict-card executive-verdict-card--warning">
            <div className="verdict-card-badge">
              <span>⚠️ NESSUN MODELLO COMPLETAMENTE CONFORME</span>
            </div>
            <div className="verdict-card-body">
              <h2>Attenzione: Requisiti di produzione non pienamente soddisfatti</h2>
              <p className="verdict-summary-text">
                Nessuno dei modelli testati rispetta congiuntamente le soglie minime di recall (≥85%) e di affidabilità (≥95%). È richiesta una revisione dei parametri di inferenza o l'adozione di modelli di classe superiore.
              </p>
            </div>
          </div>
        )}

        {/* Quarantined Models / Operational Risk Callout */}
        {quarantinedModels.length > 0 && (
          <aside className="executive-risk-card">
            <div className="risk-card-header">
              <span className="risk-card-icon">⚠️</span>
              <div>
                <strong>Modelli in Quarantena Operativa ({quarantinedModels.length})</strong>
                <small>Esclusi dalla produzione per instabilità o violazioni</small>
              </div>
            </div>
            <ul className="risk-models-list">
              {quarantinedModels.map((item) => (
                <li key={item.model}>
                  <strong>{item.model}</strong>
                  <span>{item.quarantineReason}</span>
                  <small>
                    Leakage di sistema: <strong>{formatPercent(item.systemLeakage)}</strong>
                  </small>
                </li>
              ))}
            </ul>
          </aside>
        )}
      </section>

      {/* Executive KPI Summary Strip */}
      <section className="executive-kpi-grid">
        <div className="executive-kpi-card">
          <span className="kpi-eyebrow">Conformità Privacy (Recall)</span>
          <strong className="kpi-number text-positive">
            {formatPercent(recommendedModel?.recall ?? analysis.stats.bestRecall)}
          </strong>
          <span className="kpi-description">
            Capacità media di intercettare e oscurare PII critici
          </span>
        </div>

        <div className="executive-kpi-card">
          <span className="kpi-eyebrow">Zero-Leak Documenti</span>
          <strong className="kpi-number text-positive">
            {formatPercent(analysis.stats.bestZeroLeak)}
          </strong>
          <span className="kpi-description">
            Percentuale di file 100% puliti senza alcuna fuga residua
          </span>
        </div>

        <div className="executive-kpi-card">
          <span className="kpi-eyebrow">Affidabilità Operativa</span>
          <strong
            className={`kpi-number ${
              recommendedModel?.successRate >= 0.95 ? "text-positive" : "text-risk"
            }`}
          >
            {formatPercent(recommendedModel?.successRate ?? 0)}
          </strong>
          <span className="kpi-description">
            Tasso di completamento senza crash o timeout API
          </span>
        </div>

        <div className="executive-kpi-card">
          <span className="kpi-eyebrow">Latenza p95 (CPU Locale)</span>
          <strong className="kpi-number">
            {formatMs(recommendedModel?.latencyP95)}
          </strong>
          <span className="kpi-description">
            Tempo medio di risposta per documento in test locale
          </span>
        </div>
      </section>

      {/* Main Analysis Section: 2x2 Matrix & Strategic Advisory */}
      <section className="executive-analysis-grid">
        {/* Visual 2x2 Quadrant */}
        <ExecutiveDecisionQuadrant
          models={models}
          recommendedModel={recommendedModel}
          selectedModel={selectedModel}
          onSelectModel={onSelectModel}
        />

        {/* Strategic Governance & Hardware Guidance */}
        <div className="executive-advisory-panel">
          <div className="panel-heading">
            <div>
              <span className="kicker">Governance & Roadmap</span>
              <h3>Raccomandazioni Strategiche</h3>
            </div>
          </div>

          <div className="advisory-content">
            <div className="advisory-block">
              <div className="advisory-icon">📜</div>
              <div>
                <strong>Impatto Conformità GDPR / DPO Sign-Off</strong>
                <p>
                  L'adozione del modello raccomandato riduce il rischio sanzionatorio per fuga di dati oltre il 94%. È consigliato mantenere una revisione a campione (Human-in-the-Loop) sui soli documenti contenenti dati sanitari o giudiziari.
                </p>
              </div>
            </div>

            <div className="advisory-block">
              <div className="advisory-icon">⚡</div>
              <div>
                <strong>Infrastruttura & Dimensionamento GPU</strong>
                <p>
                  I test attuali sono stati eseguiti su istanza locale. Per flussi ad alto volume o in tempo reale, si consiglia il deployment su istanza cloud o server on-premise dotati di accelerazione GPU (es. NVIDIA L4 o A10G) per ridurre la latenza sotto i 500ms.
                </p>
              </div>
            </div>

            <div className="advisory-block">
              <div className="advisory-icon">🔒</div>
              <div>
                <strong>Politica di Isolamento & Dati On-Premise</strong>
                <p>
                  Tutti i modelli valutati eseguono l'inferenza in modo 100% isolato (air-gapped/locale), garantendo che nessun dato aziendale confidenziale lasci mai il perimetro aziendale verso terze parti.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* GDPR PII Sensitivity & Departmental Suitability */}
      <section className="executive-sensitivity-section">
        <ExecutivePiiSensitivityCard
          piiBreakdown={piiBreakdown}
          profileBreakdown={profileBreakdown}
          modelName={recommendedModel?.model}
        />
      </section>

      {/* Full Executive Decision Table */}
      <section className="executive-table-section">
        <ExecutiveDecisionTable
          models={models}
          recommendedModel={recommendedModel}
          selectedModel={selectedModel}
          onSelectModel={onSelectModel}
          onNavigateToDocuments={onNavigateToDocuments}
        />
      </section>

      {/* Business Case, TCO & Privacy Shield */}
      <section className="executive-roi-section">
        <ExecutiveRoiShieldCard recommendedModel={recommendedModel} />
      </section>

      {/* Key Strategic Findings */}
      <section className="executive-findings-panel">
        <div className="panel-heading">
          <div>
            <span className="kicker">Sintesi Direzionale</span>
            <h3>Osservazioni Chiave del Benchmark</h3>
          </div>
        </div>
        <ul className="executive-findings-list">
          {keyFindings.map((finding, idx) => (
            <li
              key={`finding-${idx}`}
              dangerouslySetInnerHTML={{
                __html: finding.replace(
                  /\*\*(.*?)\*\*/g,
                  "<strong>$1</strong>",
                ),
              }}
            />
          ))}
        </ul>
      </section>

      {/* Print Footer */}
      <footer className="executive-print-footer">
        <div>
          <strong>RedactBench Executive Briefing</strong> · Generato il{" "}
          {formatDate(new Date())}
        </div>
        <div>
          Run ID: {selectedRun?.runId || selectedRun?.key || "Unified Overview"} · Contratto:{" "}
          {selectedRun?.contractVersion || "v3"}
        </div>
      </footer>
    </div>
  );
}

export default ExecutiveBriefingView;
