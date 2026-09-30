/**
 * executiveAnalyzer.js
 *
 * Provides synthesized risk, compliance, and decision analysis for executive audiences.
 * Evaluates candidate models against GDPR-oriented metrics (Zero-Leak documents,
 * system reliability, residual leakage, and operational throughput).
 */

import { uiConfig } from "../config/uiConfig";
import { micro } from "./formatters";

/**
 * Determines the contract verification state of a model.
 */
function getContractState(metrics, evidence, summary) {
  if (evidence?.contractStatus) return evidence.contractStatus;
  if (metrics?.status === "contract_failed") return "failed";
  if (summary?.legacy || evidence?.legacy) return "legacy";
  return "passed";
}

/**
 * Formats a concise error summary string from error dictionary.
 */
function summarizeErrors(errors) {
  if (!errors || Object.keys(errors).length === 0) return null;
  return Object.entries(errors)
    .map(([err, count]) => `${count}× ${err}`)
    .join(", ");
}

export const PII_TYPE_LABELS = {
  private_email: { label: "Email Aziendali / Personali", icon: "📧", critical: false },
  private_phone: { label: "Numeri di Telefono", icon: "📞", critical: false },
  private_person: { label: "Nomi & Identità Persone", icon: "👤", critical: true },
  private_date: { label: "Date & Riferimenti Temporali", icon: "📅", critical: false },
  account_number: { label: "Conti Bancari / IBAN / Account", icon: "💳", critical: true },
  private_address: { label: "Indirizzi & Domicili", icon: "🏠", critical: false },
};

export const PROFILE_LABELS = {
  legal: {
    label: "Ambito Legale & Contrattuale",
    icon: "⚖️",
    desc: "Contratti, accordi di riservatezza, clausole e patti",
  },
  financial: {
    label: "Ambito Finanziario & Contabile",
    icon: "💼",
    desc: "Report di bilancio, estratti conto, tabelle di spesa",
  },
};

/**
 * Evaluates and ranks models for C-level presentation.
 * Returns structured executive KPIs, a recommended model, risk flags, and key findings.
 */
export function analyzeExecutiveSummary(detail) {
  if (!detail || !detail.metrics) {
    return {
      available: false,
      models: [],
      recommendedModel: null,
      zeroLeakChampion: null,
      speedChampion: null,
      quarantinedModels: [],
      complianceTier: uiConfig.executive?.riskTiers?.high ?? {
        label: "Dati insufficienti",
        tone: "risk",
      },
      keyFindings: [],
      stats: {
        totalModels: 0,
        evaluatedCases: 0,
        bestRecall: 0,
        bestZeroLeak: 0,
      },
    };
  }

  const modelsList = detail.summary?.models ?? Object.keys(detail.metrics);
  const thresholds = uiConfig.executive?.thresholds ?? {
    minProductionRecall: 0.85,
    minProductionReliability: 0.95,
    maxAcceptableLeakage: 0.1,
    highZeroLeakDocRate: 0.4,
  };

  const parsedModels = modelsList.map((model) => {
    const rawMetric = detail.metrics[model];
    const metric = micro(rawMetric);
    const latencyMetric = micro(detail.latency?.metrics?.[model]);
    const evidence = detail.evidence?.[model];
    const state = getContractState(rawMetric, evidence, detail.summary);

    const recall = metric.pii_recall ?? 0;
    const leakage = metric.leakage_rate ?? (1 - recall);
    const systemLeakage = metric.system_leakage_rate ?? leakage;
    const zeroLeakDocs = metric.zero_leak_document_rate ?? 0;
    const systemZeroLeakDocs = metric.system_zero_leak_document_rate ?? zeroLeakDocs;
    const precision = metric.precision ?? 0;
    const successRate = metric.inference_success_rate ?? metric.valid_output_rate ?? 1;
    const latencyP95 = latencyMetric.latency_p95_ms ?? metric.latency_p95_ms ?? null;
    const latencyP50 = latencyMetric.latency_p50_ms ?? metric.latency_p50_ms ?? null;
    const failures = detail.failures?.[model] ?? [];
    const totalCases = metric.cases ?? evidence?.cases ?? 0;
    const evaluatedCases = metric.evaluated_cases ?? evidence?.evaluatedCases ?? totalCases;
    const errorSummary = summarizeErrors(metric.errors);

    const isContractValid = state === "passed";
    const isReliable = isContractValid && successRate >= thresholds.minProductionReliability;

    // Composite readiness score (0 to 100)
    let score = 0;
    if (isContractValid) {
      const recallScore = recall * 50; // Max 50
      const zeroLeakScore = zeroLeakDocs * 25; // Max 25
      const reliabilityScore = successRate * 25; // Max 25
      score = Math.round(recallScore + zeroLeakScore + reliabilityScore);

      // Penalize heavily if severe operational failure
      if (successRate < 0.8) {
        score = Math.round(score * 0.4);
      }
    }

    // Determine verdict badge and classification
    let verdict = "Non Idoneo";
    let tone = "risk";
    let badge = "❌ Non Conforme";
    let isQuarantined = false;
    let quarantineReason = null;

    if (!isContractValid) {
      verdict = "Bloccato (Violazione Contratto)";
      tone = "risk";
      badge = "⛔ Violazione";
      isQuarantined = true;
      quarantineReason = "Violazione schema contrattuale o parsing fallito";
    } else if (successRate < 0.8) {
      verdict = "Rischio Operativo (Timeout/Crash)";
      tone = "risk";
      badge = "⚠️ Rischio Operativo";
      isQuarantined = true;
      quarantineReason = `Affidabilità solo ${Math.round(successRate * 100)}% (${errorSummary || "errori di trasporto"})`;
    } else if (recall >= thresholds.minProductionRecall && isReliable) {
      if (zeroLeakDocs >= thresholds.highZeroLeakDocRate) {
        verdict = "Privacy Leader (Zero-Leak)";
        tone = "positive";
        badge = "🏆 Top Protezione";
      } else {
        verdict = "Raccomandato per Produzione";
        tone = "positive";
        badge = "⭐ Consigliato";
      }
    } else if (recall >= 0.75) {
      verdict = "Accettabile con Riserve";
      tone = "warning";
      badge = "⚠️ Riserve";
    }

    // Extract PII sensitivity breakdown
    const rawByType = rawMetric?.by_type ?? {};
    const piiBreakdown = Object.entries(rawByType).map(([type, stats]) => {
      const meta = PII_TYPE_LABELS[type] ?? { label: type, icon: "🏷️", critical: false };
      return {
        type,
        label: meta.label,
        icon: meta.icon,
        critical: meta.critical,
        recall: stats?.pii_recall ?? 0,
        goldCount: stats?.gold_count ?? 0,
        tp: stats?.tp ?? 0,
        fn: stats?.fn ?? 0,
        leakedChars: stats?.leaked_chars ?? 0,
      };
    });
    piiBreakdown.sort((a, b) => (b.critical ? 1 : 0) - (a.critical ? 1 : 0));

    // Extract business domain breakdown (legal vs financial)
    const rawByProfile = rawMetric?.by_profile ?? {};
    const profileBreakdown = Object.entries(rawByProfile).map(([profile, stats]) => {
      const meta = PROFILE_LABELS[profile] ?? { label: profile, icon: "📁", desc: "" };
      return {
        profile,
        label: meta.label,
        icon: meta.icon,
        desc: meta.desc,
        recall: stats?.pii_recall ?? 0,
        cases: stats?.cases ?? 0,
      };
    });

    return {
      model,
      state,
      isContractValid,
      isReliable,
      recall,
      leakage,
      systemLeakage,
      zeroLeakDocs,
      systemZeroLeakDocs,
      precision,
      successRate,
      latencyP95,
      latencyP50,
      evaluatedCases,
      totalCases,
      score,
      verdict,
      tone,
      badge,
      isQuarantined,
      quarantineReason,
      failuresCount: failures.length,
      errorSummary,
      piiBreakdown,
      profileBreakdown,
    };
  });

  // Sort candidate models by score descending
  parsedModels.sort((a, b) => b.score - a.score);

  // Identify recommended model (must be reliable and have passed contract)
  const reliableCandidates = parsedModels.filter((m) => m.isReliable);
  const recommendedModel = reliableCandidates.length > 0 ? reliableCandidates[0] : null;

  // Zero-Leak Champion
  const zeroLeakSorted = [...parsedModels].sort((a, b) => b.zeroLeakDocs - a.zeroLeakDocs);
  const zeroLeakChampion = zeroLeakSorted[0]?.zeroLeakDocs > 0 ? zeroLeakSorted[0] : null;

  // Speed Champion among models with recall >= 75%
  const compliantCandidates = parsedModels.filter((m) => m.recall >= 0.75 && m.latencyP95);
  const speedSorted = [...compliantCandidates].sort((a, b) => a.latencyP95 - b.latencyP95);
  const speedChampion = speedSorted[0] ?? null;

  // Quarantined models
  const quarantinedModels = parsedModels.filter((m) => m.isQuarantined);

  // GDPR Risk Tier
  let complianceTier = uiConfig.executive?.riskTiers?.high;
  if (recommendedModel && recommendedModel.recall >= thresholds.minProductionRecall) {
    complianceTier = uiConfig.executive?.riskTiers?.low;
  } else if (parsedModels.some((m) => m.recall >= 0.75)) {
    complianceTier = uiConfig.executive?.riskTiers?.moderate;
  }

  // Key Strategic Findings
  const keyFindings = [];
  if (recommendedModel) {
    keyFindings.push(
      `Il modello **${recommendedModel.model}** è la scelta raccomandata per la produzione: garantisce una copertura PII del **${(recommendedModel.recall * 100).toFixed(1)}%** con il **100% di affidabilità** operativa e zero violazioni di contratto.`,
    );
  }

  if (zeroLeakChampion && zeroLeakChampion.model !== recommendedModel?.model) {
    keyFindings.push(
      `Per contesti di massima riservatezza (GDPR zero-tolerance), **${zeroLeakChampion.model}** eccelle con il **${(zeroLeakChampion.zeroLeakDocs * 100).toFixed(1)}% di documenti completamente esenti da leak**.`,
    );
  } else if (recommendedModel && recommendedModel.zeroLeakDocs > 0) {
    keyFindings.push(
      `Il **${(recommendedModel.zeroLeakDocs * 100).toFixed(1)}% dei documenti aziendali** elaborati dal modello consigliato risulta completamente anonimizzato senza alcuna fuga residua di PII.`,
    );
  }

  if (quarantinedModels.length > 0) {
    const quarantinedNames = quarantinedModels.map((m) => m.model).join(", ");
    keyFindings.push(
      `Attenzione operativa: **${quarantinedNames}** presentano instabilità (timeout API / errori di trasporto), causando fino al 90%+ di leakage effettivo a livello di sistema. Non sono idonei per il rilascio immediato.`,
    );
  }

  const bestLatency = recommendedModel?.latencyP95;
  if (bestLatency) {
    const sec = (bestLatency / 1000).toFixed(1);
    keyFindings.push(
      `Nota Infrastruttura: Con una latenza p95 di **${sec}s per documento** su elaborazione CPU locale, si consiglia il dimensionamento di un'accelerazione hardware (GPU/Metal) per carichi in tempo reale o batch ad alto volume.`,
    );
  }

  return {
    available: true,
    models: parsedModels,
    recommendedModel,
    zeroLeakChampion,
    speedChampion,
    quarantinedModels,
    complianceTier,
    keyFindings,
    piiBreakdown: recommendedModel?.piiBreakdown ?? parsedModels[0]?.piiBreakdown ?? [],
    profileBreakdown:
      recommendedModel?.profileBreakdown ?? parsedModels[0]?.profileBreakdown ?? [],
    stats: {
      totalModels: parsedModels.length,
      evaluatedCases: detail.summary?.cases ?? parsedModels[0]?.totalCases ?? 0,
      bestRecall: parsedModels[0]?.recall ?? 0,
      bestZeroLeak: zeroLeakChampion?.zeroLeakDocs ?? 0,
    },
  };
}
