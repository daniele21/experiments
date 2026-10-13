import { CAPABILITY_DEFS } from "./capabilitySummary.js";

export const MATRIX_METRICS = Object.freeze([
  { id:"recall", label:"Recall PII", direction:"higher",
    description:"Percentuale di PII gold riconosciute. Le inferenze fallite restano nel denominatore." },
  { id:"fp", label:"Falsi positivi", direction:"lower",
    description:"Percentuale di casi senza PII gold con almeno un falso positivo; solo risposte valide." },
  { id:"coverage", label:"Run validi", direction:"higher",
    description:"Percentuale di documenti con inferenza valida sul totale dei casi del benchmark." },
]);

export function matrixMetric(model, metric) {
  if (!model) return null;
  const ratio = metric === "recall"
    ? (model.totalGold > 0 ? model.positiveRecall : null)
    : metric === "fp"
      ? (model.negativeValidated > 0 ? model.negativeFalsePositiveRate : null)
      : metric === "coverage"
        ? (model.documents > 0 ? model.validDocuments / model.documents : null)
        : null;
  return typeof ratio === "number" && Number.isFinite(ratio) && ratio >= 0 && ratio <= 1
    ? ratio : null;
}

// Semantically fixed thresholds, NEVER relative to a given row/column.
// Equal percentages share a color irrespective of dataset or model.
export function matrixTone(value, metric) {
  if (value === null) return "unavailable";
  if (metric === "fp") return value <= .05 ? "good" : value <= .20 ? "medium" : "low";
  if (metric === "coverage") return value >= .98 ? "good" : value >= .90 ? "medium" : "low";
  return value >= .90 ? "good" : value >= .75 ? "medium" : "low";
}

export function buildModelDatasetMatrix(latest) {
  const datasets = CAPABILITY_DEFS.map(def => ({
    ...def, report: latest?.[def.id] ?? null,
  }));
  const ids = new Set();
  for (const entry of datasets) for (const model of entry.report?.models ?? []) {
    if (model?.modelId) ids.add(model.modelId);
  }
  const modelIds = [...ids].sort((a,b) => a.localeCompare(b, "en", {numeric:true}));
  const rows = modelIds.map(modelId => ({
    modelId,
    cells: Object.fromEntries(datasets.map(({id,report}) => [
      id, report?.models?.find(m => m.modelId === modelId) ?? null,
    ])),
  }));
  return {
    datasets, rows,
    measured: rows.reduce((sum,row) => sum+datasets.filter(d => Boolean(row.cells[d.id])).length,0),
  };
}
