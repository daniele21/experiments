import { useEffect, useMemo, useState } from "react";
import { appRoutes } from "../routing";
import ThemeToggle from "../components/ThemeToggle";
import DocumentComparison from "../v2/DocumentComparison";
import DocumentWorkspace from "../v2/DocumentWorkspace";
import CapabilityMatrix from "../v2/ModelDatasetMatrixView.jsx";
import { selectLatestCapabilityRuns } from "../v2/capabilitySummary.js";
import { modelEvidence, modelsIn, ratioText, shortModel, timeText, isNumber } from "../v2/evidence";
import { datasetInfo, groupExperiments, qualityRuns, runDate, executionLabel } from "./experimentCatalog.js";
import "../v2/base.css";
import "./workspace.css";

const TYPE_LABELS = {
  clinical_procedure: "Procedure cliniche", clinical_symptom: "Sintomi", clinical_disease: "Patologie",
  clinical_chemical: "Sostanze chimiche", clinical_protein: "Proteine", health_condition: "Condizioni di salute",
  private_person: "Nomi di persona", private_email: "Indirizzi email", private_phone: "Numeri di telefono",
  private_address: "Indirizzi", private_date: "Date personali", account_number: "Identificativi",
};

function Icon({ name, size = 20 }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    chart: <><path d="M4 4v16h17M9 15v-4m5 4V7m5 8v-5"/></>,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5"/>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8.5 12 2.5 2.5 4.5-5"/></>,
    refresh: <><path d="M20 8a8 8 0 1 0 .1 8M20 3v5h-5"/></>,
    settings: <><path d="M5 7h14M5 17h14"/><circle cx="9" cy="7" r="2"/><circle cx="15" cy="17" r="2"/></>,
    file: <><path d="M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 13h8m-8 4h5"/></>,
    print: <><path d="M7 8V3h10v5M7 16H4V8h16v8h-3M7 13h10v8H7z"/></>,
    chevron: <path d="m9 5 7 7-7 7"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] ?? paths.file}</svg>;
}

function Status({ run }) {
  return <span className={`rg-status ${run.legacy ? "rg-status--muted" : run.status === "complete" ? "" : "rg-status--partial"}`}>
    <i/>{run.status === "complete" ? "Completato" : "Parziale"}{run.legacy ? " · storico" : ""}
  </span>;
}

function Catalog({ runs, groups, dataset, onDataset, onOpenRun, loading }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [limit, setLimit] = useState(8);
  const selected = groups.find(g => g.id === dataset);
  const rows = qualityRuns(runs).filter(run => {
    const info = datasetInfo(run.dataset);
    return (!selected || info.id === selected.id) &&
      (status === "all" || run.status === status) &&
      `${info.title} ${info.short} ${run.runId} ${run.cases} ${run.models?.join(" ")} ${runDate(run.createdAt)}`.toLowerCase().includes(query.toLowerCase().trim());
  });
  const modelCount = new Set(runs.flatMap(r => r.models ?? [])).size;
  return <>
    <div className="rg-page-heading">
      <div><span className="rg-eyebrow">RISULTATI DEL BENCHMARK</span><h1>{selected?.title ?? "Risultati di anonimizzazione."}</h1>
        <p>{selected ? `${selected.description}. Scegli l’esecuzione da presentare o approfondire.` : "Esplora i dataset, presenta i risultati e risali alle evidenze."}</p></div>
      {selected && <button type="button" className="rg-button" onClick={() => onDataset(null)}>Tutti i dataset <Icon name="grid" size={16}/></button>}
    </div>
    {!selected && <>
      <div className="rg-library-stats" aria-label="Inventario locale">
        <span><strong>{groups.filter(g => g.id !== "unknown").length}</strong> dataset identificati</span><span><strong>{qualityRuns(runs).length}</strong> esecuzioni</span><span><strong>{modelCount}</strong> modelli</span>
        <span className="rg-library-note">Dalle misure al singolo caso</span>
      </div>
      <section className="rg-dataset-grid" aria-label="Dataset del benchmark">
        {groups.map(group => <button type="button" key={group.id} className={`rg-dataset-card rg-tone-${group.tone}`} onClick={() => { onDataset(group.id); setLimit(8); }}>
          <span className="rg-dataset-card-top"><span className="rg-dataset-symbol"><Icon name={group.id === "realistic" ? "file" : "shield"} size={22}/></span><span className="rg-dataset-code">{group.short}{group.language && <> / {group.language}</>}</span><Icon name="arrow" size={18}/></span>
          <h2>{group.title}</h2><p>{group.description}</p>
          <span className="rg-dataset-card-bottom"><span>{group.runs.length} {group.runs.length === 1 ? "esecuzione" : "esecuzioni"} · {group.models.length} modelli</span><span>{runDate(group.runs[0]?.createdAt)}</span></span>
        </button>)}
      </section>
    </>}
    <section className="rg-panel rg-executions">
      <div className="rg-section-heading"><div><h2>{selected ? "Esecuzioni del dataset" : "Esplora le esecuzioni"}</h2><p>Ogni riga è una prova distinta. Data, casi e modelli identificano il confronto.</p></div><span className="rg-count">{rows.length} risultati</span></div>
      <div className="rg-table-tools">
        <label className="rg-search"><Icon name="search" size={17}/><input aria-label="Cerca esperimenti" placeholder="Cerca dataset, modello, numero di casi…" value={query} onChange={e => { setQuery(e.target.value); setLimit(8); }}/></label>
        <label className="rg-select-label">Stato <select value={status} onChange={e => { setStatus(e.target.value); setLimit(8); }}><option value="all">Tutti</option><option value="complete">Completati</option><option value="incomplete">Parziali</option></select></label>
      </div>
      <div className="rg-table-scroll"><table className="rg-table"><thead><tr><th>Esperimento</th><th>Data</th><th>Casi</th><th>Modelli</th><th>Stato</th><th><span className="rg-sr-only">Apri</span></th></tr></thead>
        <tbody>{rows.slice(0, limit).map(run => {
          const info = datasetInfo(run.dataset);
          return <tr key={run.key}><td><button className="rg-table-link" onClick={() => onOpenRun(run.key)}><span className={`rg-mini-icon rg-tone-${info.tone}`}><Icon name="file" size={17}/></span><span><strong>{info.title}</strong><small>{run.suiteId ?? run.runId}</small></span></button></td>
            <td className="rg-nowrap">{runDate(run.createdAt, true)}</td><td><strong>{run.cases ?? "—"}</strong></td><td><span title={run.models?.map(shortModel).join(", ")}>{run.models?.length ?? 0} modelli</span></td><td><Status run={run}/></td>
            <td><button className="rg-icon-button" title={`Apri ${executionLabel(run)}`} aria-label={`Apri ${info.title}, ${executionLabel(run)}`} onClick={() => onOpenRun(run.key)}><Icon name="arrow" size={18}/></button></td></tr>;
        })}</tbody></table></div>
      {!rows.length && <div className="rg-empty"><Icon name="search" size={28}/><h3>{loading ? "Caricamento degli esperimenti…" : "Nessun esperimento trovato"}</h3><p>{query || status !== "all" ? "Prova un’altra ricerca o modifica il filtro sullo stato." : "I risultati locali compariranno qui appena disponibili."}</p></div>}
      {rows.length > limit && <div className="rg-table-footer"><span>Mostrate {limit} di {rows.length} esecuzioni</span><button className="rg-button" onClick={() => setLimit(n => n + 12)}>Mostra altre esecuzioni</button></div>}
    </section>
    <div className="rg-library-footnote"><Icon name="shield" size={16}/><p>Ogni risultato mantiene il proprio dataset e la propria esecuzione. Le prove su dataset diversi non vengono sommate in un punteggio unico.</p></div>
  </>;
}

function RunResults({ detail, selectedModel, onSelectModel, onDocuments }) {
  const models = modelsIn(detail);
  const rows = models.map(model => {
    const row = modelEvidence(detail, model);
    const metrics = detail.metrics?.[model];
    const failed = metrics?.status === "contract_failed";
    return { ...row, failed, microRecall: failed ? null : row.microRecall };
  });
  const selected = rows.find(r => r.model === selectedModel) ?? rows[0];
  const usable = rows.filter(r => isNumber(r.microRecall));
  const best = [...usable].sort((a,b) => b.microRecall - a.microRecall)[0];
  const sameRun = detail.summary?.status === "complete" && !detail.summary?.legacy && detail.summary?.source !== "overview";
  const goldScope = detail.manifest?.gold_scope;
  const typeRows = Object.entries(detail.metrics?.[selected?.model]?.by_type ?? {})
    .filter(([, value]) => value.gold_count > 0)
    .sort((a,b) => (b[1].fn ?? 0) - (a[1].fn ?? 0)).slice(0, 7);
  const bestCount = best ? usable.filter(r => r.microRecall === best.microRecall).length : 0;
  return <>
    <section className="rg-result-story">
      <div className="rg-story-copy"><span className="rg-eyebrow">IL RISULTATO IN BREVE</span>
        <h2>{!sameRun ? "Un risultato da leggere nel suo contesto." : !best ? "La copertura non è disponibile per questa prova." : bestCount > 1 ? "La copertura migliore è condivisa da più modelli." : `${shortModel(best.model)} ha la copertura più alta in questa prova.`}</h2>
        <p>{sameRun && best ? <>Il modello rileva il <strong>{ratioText(best.microRecall)}</strong> delle entità annotate, includendo l’effetto degli errori di inferenza. Il confronto riguarda solo questa esecuzione.</> : "Consulta le singole misure e lo stato di valutazione prima di confrontare i modelli."}</p>
        <button className="rg-text-button" onClick={onDocuments}>Esamina i casi e gli errori <Icon name="arrow" size={17}/></button>
      </div>
      <div className="rg-story-scope"><Icon name="shield" size={24}/><strong>Il perimetro della misura</strong><p>{goldScope === "injected_only" ? "Il gold contiene solo le PII inserite nel corpus: il risultato non misura la protezione completa del documento." : "Le percentuali si riferiscono alle annotazioni gold del dataset, non a una garanzia di anonimizzazione completa."}</p><span>Test sperimentale · {detail.summary?.cases ?? "—"} casi</span></div>
    </section>
    <section className="rg-panel">
      <div className="rg-section-heading"><div><h2>Come si comportano i modelli</h2><p>Metriche di questa esecuzione. Seleziona un modello per vedere dove sbaglia.</p></div><span className="rg-count">{models.length} modelli</span></div>
      <div className="rg-table-scroll"><table className="rg-table rg-model-table"><thead><tr><th>Modello</th><th>Copertura del gold ↑</th><th>Entità mancate ↓</th><th>Rilevazioni extra ↓</th><th>Inferenze riuscite ↑</th><th>Latenza p50 ↓</th></tr></thead><tbody>
        {rows.map(row => <tr key={row.model} className={selected?.model === row.model ? "rg-row-selected" : ""}>
          <td><button className="rg-table-link" aria-pressed={selected?.model === row.model} onClick={() => onSelectModel(row.model)}><span className="rg-model-dot"/><span><strong>{shortModel(row.model)}</strong><small>{row.failed ? "Output non valido" : row.cacheVerified ? "Qualità e latenza verificata" : "Misure di qualità"}</small></span></button></td>
          <td><div className="rg-score"><strong>{ratioText(row.microRecall)}</strong><span><i style={{width:`${isNumber(row.microRecall) ? Math.max(0,Math.min(100,row.microRecall*100)) : 0}%`}}/></span></div></td>
          <td>{row.failed ? "—" : row.falseNegatives ?? "—"}</td><td>{row.failed ? "—" : row.falsePositives ?? "—"}</td><td>{ratioText(row.success)}</td><td>{timeText(row.p50)}</td>
        </tr>)}
      </tbody></table></div>
      <div className="rg-inline-note">↑ Più alto è meglio &nbsp; ↓ Più basso è meglio &nbsp; · &nbsp; “—” indica una misura non disponibile o non verificata.</div>
    </section>
    <div className="rg-analysis-grid">
      <section className="rg-panel"><div className="rg-section-heading"><div><h2>Dove perde copertura</h2><p>{selected ? shortModel(selected.model) : "Seleziona un modello"} · categorie con annotazioni gold</p></div></div>
        <div className="rg-type-list">{!selected?.failed && typeRows.length ? typeRows.map(([type, value]) => <div className="rg-type-row" key={type}><span>{TYPE_LABELS[type] ?? type.replaceAll("_", " ")}</span><span className="rg-type-track"><i style={{width:`${isNumber(value.pii_recall) ? Math.max(0,Math.min(100,value.pii_recall*100)) : 0}%`}}/></span><strong>{ratioText(value.pii_recall)}</strong></div>) : <p className="rg-muted">Distribuzione per categoria non disponibile.</p>}</div>
      </section>
      <section className="rg-panel rg-reading-guide"><span className="rg-eyebrow">COME LEGGERE IL RISULTATO</span><h2>Tre domande, prima di scegliere.</h2><dl><div><dt>Quanto rileva?</dt><dd>La copertura misura quante entità annotate vengono trovate.</dd></div><div><dt>Cosa lascia esposto?</dt><dd>Le entità mancate sono gli elementi del gold non rilevati dal modello.</dd></div><div><dt>Cosa oscura in più?</dt><dd>Le rilevazioni extra non corrispondono al gold. La loro interpretazione dipende dalla completezza delle annotazioni.</dd></div></dl></section>
    </div>
    <details className="rg-provenance"><summary>Provenienza e dettagli tecnici dell’esecuzione</summary><dl><div><dt>Identificativo</dt><dd>{detail.summary?.suiteId ?? detail.summary?.runId}</dd></div><div><dt>Dataset</dt><dd>{detail.manifest?.dataset ?? detail.summary?.dataset}</dd></div><div><dt>Schema</dt><dd>{detail.summary?.evaluationSchema ?? "Non indicato"}</dd></div><div><dt>Gold</dt><dd>{goldScope ?? "Ambito non dichiarato"}</dd></div><div><dt>Commit</dt><dd>{detail.manifest?.benchmark_commit ?? "Non indicato"}</dd></div></dl></details>
  </>;
}

function DatasetComparison({ onOpenRun, refreshToken }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/capabilities", { signal: controller.signal }).then(r => { if (!r.ok) throw Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { setData(d.capabilities ?? []); setError(null); }).catch(e => { if (e.name !== "AbortError") setError(e.message); });
    return () => controller.abort();
  }, [refreshToken]);
  const latest = useMemo(() => selectLatestCapabilityRuns(data ?? []), [data]);
  return <><div className="rg-page-heading"><div><span className="rg-eyebrow">VISTA TRASVERSALE</span><h1>Un confronto, dataset per dataset.</h1><p>L’ultima misura disponibile per ogni modello. Apri una cella per risalire all’esecuzione originale.</p></div></div>
    <div className="rg-comparison-note"><Icon name="chart"/><p>I dataset misurano capacità diverse. Ogni colonna resta indipendente; non viene calcolata una classifica globale.</p></div>
    {error ? <div role="alert" className="rg-error">Impossibile leggere i confronti: {error}</div> : !data ? <div className="rg-empty">Caricamento dei confronti…</div> : <div className="rg-cross-dataset"><CapabilityMatrix latest={latest} onSelectCell={(category, model) => { const evidence = latest[category]?.models.find(m => m.modelId === model); if (evidence) onOpenRun(evidence.runKey, model); }}/></div>}
  </>;
}

export default function BenchmarkWorkspace({ route, runs, detail, selectedKey, selectedModel, onSelectModel, onRefresh, loading, refreshing, error, lastRefresh }) {
  const groups = useMemo(() => groupExperiments(runs), [runs]);
  const page = route.page;
  const home = page === "experiments" || page === "executive";
  const comparing = page === "capabilities";
  const dataset = route.searchParams.get("dataset");
  const current = runs.find(r => r.key === selectedKey);
  const info = datasetInfo(current?.dataset);
  const sameDatasetRuns = qualityRuns(runs).filter(r => datasetInfo(r.dataset).id === info.id);
  const ready = detail && detail.summary?.key === selectedKey && !loading;
  const models = ready ? modelsIn(detail) : [];
  const [secondModel, setSecondModel] = useState(null);
  const first = models.includes(selectedModel) ? selectedModel : models[0];
  const second = models.find(m => m === secondModel && m !== first) ?? models.find(m => m !== first);
  const pair = [first, second].filter(Boolean);
  function navigate(path, runKey = null, datasetId = null) {
    const search = new URLSearchParams();
    if (runKey) search.set("run", runKey);
    if (datasetId) search.set("dataset", datasetId);
    route.navigate(path, { preserveSearch: false, searchParams: search });
  }
  function openRun(key, model = null) {
    if (model) onSelectModel(model);
    navigate(appRoutes.clientModels, key);
  }
  function openDataset(id) { navigate(appRoutes.clientExperiments, null, id); }
  return <div className="rg-workspace">
    <a className="rg-skip" href="#rg-main">Vai ai risultati</a>
    <aside className="rg-sidebar">
      <button className="rg-brand" onClick={() => openDataset(null)} aria-label="RedactGuard, tutti gli esperimenti"><span className="rg-brand-mark"><Icon name="shield" size={24}/></span><span><strong>RedactGuard<span className="rg-brand-period">.</span></strong><small>BENCHMARK LAB</small></span></button>
      <span className="rg-nav-label">WORKSPACE</span>
      <nav className="rg-main-nav" aria-label="Navigazione principale"><button className={home || !comparing ? "active" : ""} aria-current={home ? "page" : undefined} onClick={() => openDataset(null)}><Icon name="grid"/>Esperimenti<span>{qualityRuns(runs).length}</span></button><button className={comparing ? "active" : ""} aria-current={comparing ? "page" : undefined} onClick={() => navigate(appRoutes.clientCapabilities)}><Icon name="chart"/>Confronto dataset</button></nav>
      <div className="rg-sidebar-datasets"><span className="rg-nav-label">I TUOI DATASET</span><nav aria-label="Dataset">{groups.map(g => <button key={g.id} className={(home ? dataset === g.id : !comparing && info.id === g.id) ? "selected" : ""} onClick={() => openDataset(g.id)}><span className={`rg-dataset-dot rg-tone-${g.tone}`}/><span>{g.title}</span><small>{g.runs.length}</small></button>)}</nav></div>
      <div className="rg-sidebar-bottom"><button className="rg-technical-link" onClick={() => navigate(appRoutes.advancedModels, current?.key)}><Icon name="settings" size={18}/>Analisi tecnica<Icon name="arrow" size={15}/></button><div className="rg-local-note"><span className="rg-live-dot"/><div><strong>Workspace locale</strong><small>Risultati letti dal tuo Mac</small></div></div></div>
    </aside>
    <div className="rg-main">
      <header className="rg-topbar"><div className="rg-breadcrumb"><button onClick={() => openDataset(null)}>Workspace</button><span>/</span><strong>{home ? "Esperimenti" : comparing ? "Confronto dataset" : info.short}</strong></div><div className="rg-top-actions"><span className="rg-sync-label">{refreshing ? "Aggiornamento…" : lastRefresh ? `Aggiornato alle ${lastRefresh.toLocaleTimeString("it-IT", { hour:"2-digit", minute:"2-digit" })}` : "Lettura risultati…"}</span><button className="rg-icon-button" aria-label="Aggiorna risultati" onClick={onRefresh}><Icon name="refresh" size={17}/></button><ThemeToggle/></div></header>
      <main id="rg-main" className="rg-page">
        {error && <div className="rg-error" role="alert">Impossibile aggiornare i risultati: {error}<button onClick={onRefresh}>Riprova</button></div>}
        {home ? <Catalog runs={runs} groups={groups} dataset={dataset} onDataset={openDataset} onOpenRun={openRun} loading={loading}/> : comparing ? <DatasetComparison onOpenRun={openRun} refreshToken={lastRefresh}/> : <>
          <div className="rg-run-heading"><div><button className="rg-back-link" onClick={() => openDataset(info.id)}>← Tutte le esecuzioni di {info.short}</button><div className="rg-run-title"><h1>{info.title}</h1>{current && <Status run={current}/>}</div><p>{current ? executionLabel(current) : "Seleziona un esperimento per vedere i risultati."}</p></div><button className="rg-button rg-print" onClick={() => window.print()} disabled={!ready}><Icon name="print" size={17}/>Stampa report</button></div>
          {current && <div className="rg-run-context"><span><strong>{current.cases ?? "—"}</strong> casi</span><span><strong>{current.models?.length}</strong> modelli</span><span>{current.pairedLatencyKey ? "Qualità + latenza" : "Valutazione di qualità"}</span><label>Esecuzione<select aria-label="Scegli esecuzione dello stesso dataset" value={selectedKey} onChange={e => openRun(e.target.value)}>{sameDatasetRuns.map(r => <option key={r.key} value={r.key}>{executionLabel(r)}</option>)}</select></label></div>}
          <nav className="rg-run-tabs" aria-label="Esplora questa esecuzione"><button className={page === "models" ? "active" : ""} aria-current={page === "models" ? "page" : undefined} onClick={() => navigate(appRoutes.clientModels, selectedKey)}>Risultati</button><button className={page === "documents" || page === "detail" ? "active" : ""} aria-current={page === "documents" || page === "detail" ? "page" : undefined} onClick={() => navigate(appRoutes.clientDocuments, selectedKey)}>Casi & errori</button><span>Una sola esecuzione, evidenze coerenti.</span></nav>
          {!ready ? <div className="rg-empty" role="status">{error ? "I risultati non sono disponibili. Riprova l’aggiornamento." : "Caricamento dell’esecuzione…"}</div> : <>
            {current?.legacy && <div className="rg-comparison-note"><p>Esecuzione storica: usa uno schema di valutazione precedente. Le metriche non sono direttamente confrontabili con quelle dello schema attuale.</p></div>}
            {page === "models" ? <RunResults detail={detail} selectedModel={selectedModel} onSelectModel={onSelectModel} onDocuments={() => navigate(appRoutes.clientDocuments, selectedKey)}/> : <>
              {models.length > 1 && <div className="rg-model-controls"><span>Confronto sui casi</span><label>Modello A<select aria-label="Modello A" value={first ?? ""} onChange={e => onSelectModel(e.target.value)}>{models.map(m => <option key={m} value={m}>{shortModel(m)}</option>)}</select></label><label>Modello B<select aria-label="Modello B" value={second ?? ""} onChange={e => setSecondModel(e.target.value)}>{models.filter(m => m !== first).map(m => <option key={m} value={m}>{shortModel(m)}</option>)}</select></label></div>}
              <div className="rg-document-area">{page === "detail" ? <DocumentWorkspace detail={detail} documentName={route.params.documentName} initialModel={route.params.model} models={[route.params.model, ...pair.filter(m => m !== route.params.model)].filter(m => models.includes(m)).slice(0,2)} onBack={() => navigate(appRoutes.clientDocuments, selectedKey)} onSelectModel={model => {onSelectModel(model);navigate(appRoutes.clientDetail(route.params.documentName,model),selectedKey);}}/> : <DocumentComparison detail={detail} models={pair} onOpenDocument={(name, model) => navigate(appRoutes.clientDetail(name,model),selectedKey)}/>}</div>
            </>}
          </>}
        </>}
        <footer className="rg-page-footer"><span>RedactGuard Benchmark Lab</span><span>Misure sperimentali · consultazione locale</span></footer>
      </main>
    </div>
  </div>;
}
