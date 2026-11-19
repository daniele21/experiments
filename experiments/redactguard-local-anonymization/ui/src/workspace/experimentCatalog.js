// Navigation identities only. Scores always come from one persisted execution.
const DATASETS = [
  { id: "spaccc", match: "spaccc", title: "Casi clinici spagnoli", short: "SPACCC", language: "ES", description: "Test clinici con annotazioni gold", tone: "teal" },
  { id: "asq", match: "asq-phi", title: "Dati clinici · ASQ", short: "ASQ-PHI", language: null, description: "Riconoscimento delle informazioni sanitarie", tone: "blue" },
  { id: "e3c", match: "e3c", title: "Casi clinici italiani", short: "E3C", language: "IT", description: "Valutazione sulle PII inserite nel corpus", tone: "violet" },
  { id: "healthcare", match: "healthcare", title: "Healthcare sintetico", short: "Healthcare", language: "IT", description: "Diagnosi, trattamenti e informazioni cliniche", tone: "rose" },
  { id: "realistic", match: "realistic", title: "Documenti realistici", short: "Realistic", language: "IT", description: "Formati e dati personali di uso quotidiano", tone: "blue" },
  { id: "challenge", match: "challenge", title: "Casi difficili", short: "Challenge", language: "IT", description: "Casi contrastivi e categorie PII complesse", tone: "amber" },
  { id: "ambiguous", match: "ambiguous", title: "PII ambigue", short: "Ambiguous", language: "IT", description: "Quando il contesto cambia cosa proteggere", tone: "violet" },
];

export function datasetInfo(value) {
  const path = String(value ?? "").replaceAll("\\", "/");
  const match = DATASETS.find(d => path.toLowerCase().replaceAll("_", "-").includes(d.match));
  if (match) return match;
  const parts = path.split("/").filter(Boolean);
  const name = parts.at(-1)?.endsWith(".jsonl") ? parts.at(-2) : parts.at(-1);
  return { id: path || "unknown", title: name || "Dataset non indicato", short: name || "Altro", description: "Risultati disponibili in locale", language: null, tone: "slate" };
}

export function qualityRuns(runs) {
  return [...runs].filter(r => r.kind !== "latency").sort((a, b) =>
    (Date.parse(b.createdAt) || 0) - (Date.parse(a.createdAt) || 0) || a.key.localeCompare(b.key));
}

export function groupExperiments(runs) {
  const groups = new Map();
  for (const run of qualityRuns(runs)) {
    const info = datasetInfo(run.dataset);
    if (!groups.has(info.id)) groups.set(info.id, { ...info, runs: [], models: new Set() });
    const group = groups.get(info.id);
    group.runs.push(run);
    for (const model of run.models ?? []) group.models.add(model);
  }
  return [...groups.values()].map(g => ({ ...g, models: [...g.models] }));
}

export function runDate(value, withTime = false) {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat("it-IT", {
    day: "numeric", month: "short", year: "numeric", ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date) : "Data non disponibile";
}

export function executionLabel(run) {
  return `${runDate(run.createdAt, true)} · ${run.cases ?? "?"} casi · ${run.models?.length ?? 0} modelli${run.status === "incomplete" ? " · parziale" : ""}`;
}
