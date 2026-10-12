# RedactBench UI 2.0 — Piano di sviluppo esecutivo

**Data:** 2026-10-12  
**Repo:** daniele21/experiments  
**Scope:** experiments/redactguard-local-anonymization/ui  
**Stato:** specifica implementativa, non UI già realizzata.  
**Design target:** mockup concordati: dark-first, gerarchia visiva forte, confronto modelli, matrice documenti, workspace documento, PII inspector.

## 1. Outcome

Ricostruire l'esperienza di lettura dei benchmark senza riscrivere il motore Python:
- capire in 5 secondi perché un modello è preferibile per protezione, velocità o trade-off;
- trovare con pochi click il file dove modelli differiscono;
- vedere una singola PII sul documento e quale modello l'ha trovata o mancata;
- restare privacy-first, con output raw e dettagli tecnici solo su richiesta.

Metriche di successo da verificare con 5 utenti: almeno 4/5 identificano senza aiuto (1) il modello più veloce, (2) il documento più problematico, (3) una PII mancata, in <=30 secondi per task. Il primo criterio decisionale va capito in <=5 secondi. Non sono risultati già misurati.

## 2. Audit dell'architettura attuale

| Modulo | Strategia | Perché |
|---|---|---|
| src/App.jsx | Scomporre in shell, data hook, pagine | Oggi contiene navigazione, fetch, KPI ed executive nella stessa unità |
| src/routing.js | Preservare ed estendere | Route client e advanced, deep link, back-forward e ?run esistono |
| vite.config.js | Mantenere API locali, estrarre adapter server | Già espone /api/runs, /api/run, /api/overview e pairing suite quality/latency |
| ClientEvaluationJourney.jsx | Rimpiazzare presentazione con pagine piccole | Mescola overview, matrice, detail |
| DocumentTextViewer.jsx e DocumentFormattedViewer.jsx | Recuperare parsing/render e split, rifattorizzare UI | Hanno già il rendering delle tabelle e il concetto di split |
| ClientDocumentPreview.jsx e DocumentSpanItem.jsx | Recuperare segmenti, coverage e masking | Dovranno condividere un solo stato selezione span |
| DocumentComparisonView.jsx | Rimpiazzare la vista con matrice compatta | Attuale visualizzazione troppo densa |
| ExecutiveBriefingView.jsx e executiveAnalyzer.js | Togliere dal percorso primario; preservare advanced durante transizione | Evitare dichiarazioni GDPR, produzione certificata e hardware non dimostrate |
| src/styles.css (grande) | Evitare ulteriori patch globali; CSS v2 scoped | Limitare collisioni e rischio regressione |

**Verità dati:** il middleware oggi legge gold, missed, overRedacted, redactions e testo canonico Markdown in docSpans. NON fornisce automaticamente il layout originale pixel-perfect dei PDF, DOCX o XLSX. Il design MVP mostra fedelmente il contenuto testuale valutato e una struttura tabellare semantica; render originale richiede progetto separato.

## 3. Information architecture finale

Tre route primarie, quattro stati UX:
- **Modelli:** /client/models, decision dashboard.
- **Documenti:** /client/documents, heatmap/matrice comparativa.
- **Documento:** /client/documents/:document/models/:model, visualizzazione full-width.
- **PII Inspector:** tab/drawer dentro Documento, non ulteriore voce sidebar.

Manteniamo le route /advanced/* per accesso a debugging storico, senza inserirne i KPI in testa alla nuova esperienza.

Topbar compatta e fissa: nome prodotto, titolo/dataset, run selezionato con data e stato, modelli in confronto (2 predefiniti, ma supporto N modelli in archivio), indicatore misure non verificate. Deep link e ?run restano validi.

Il default nella vista comparativa deve essere l'ultima **suite completata e confrontabile**, non Unified Overview (aggregato che può mescolare hardware, date o dataset). Cross-run rimane accessibile ma etichettato **Mixed evidence** e non genera vincitore assoluto.

## 4. Specifiche di pagina

### 4.1 Model Comparison — una sola domanda per volta

Header con contesto run e due model picker. Tre switch:
1. **Protezione:** hero “documenti senza leakage” e macro recall per famiglia; optional micro recall/precision in disclosure.
2. **Velocità:** p50 da inferenze dedicate, rapporto di velocità, sample size; p95 in disclosure con avviso esplorativo quando n è piccolo.
3. **Trade-off:** scatter/curve qualità vs latency con legenda e delta, mai uno score combinato opaco.

Layout desktop: due card modello della stessa dimensione, KPI hero leggibili (non 6 indicatori equivalenti), una conclusione algoritmica composta solo da evidenze calcolate, CTA “Dove differiscono?” per passare a Documenti.

**Regole decisione:** usare macro per famiglia se disponibile, altrimenti macro per documento (etichettata), altrimenti micro (con disclosure). Zero/null/contract failed non sono equivalenti. Se latenza cached o non verificata, mostrare “Latenza non confrontabile”, non rank automatico. Nessun “certificato GDPR” o “approvato per produzione”.

### 4.2 Document Comparison — la differenza salta all'occhio

Matrice con righe file e colonne: documento + estensione, #PII gold, modello A, modello B, delta. Default metrica recall con scala comune 0–100%, toggle Recall/Leakage/PII mancate; non mettere tutte le metriche insieme.
- Ordinamento default per maggior rischio o maggiore differenza; ricerca file, filtro tipo/PII/status e extension.
- Colori semantici consistenti su tutta la tabella, niente gradienti autoadattati a ciascuna cella.
- Il documento problematico emerge prima senza “mini dashboard” in ogni riga.
- Click riga -> Documento con stesso run, modelli e criterio.
- Run fallito distinto da recall 0, anche nella legenda.
- Con 11 documenti l'intera matrice deve essere leggibile in viewport desktop; con N grandi paginazione/virtualizzazione.

### 4.3 Single Document Workspace — documento dominante

Obiettivo layout desktop: canvas testuale visivamente 65–70% larghezza, inspector collassabile <=35%. Toolbar minimal: breadcrumb, nome file, modelli A/B, “Singolo / Affiancato”, “Solo differenze”, filtra tipo PII, mostra/oscura.

- Due canvas affiancati condividono fonte testuale e ancore; scroll sync per offset, non per pixel arbitrari; scelta modelli flessibile.
- XLSX/CSV: tabella semantica navigabile con celle e righe. PDF/DOCX/TXT/PPTX: lettura strutturata del testo canonico, senza promettere coordinate originali.
- Stati: **rilevata** verde, **mancata** rosso, **extra vs gold** ambra; colori identità modello separati, p.es. blu/viola.
- PII oscurate all'ingresso; reveal singola PII esplicito. Reset reveal al cambio file/run/modello; print/export per default mascherato.
- Click su annotazione -> inspector mostra quella PII; click su item inspector -> scroll/highlight al giusto offset e focus.
- 1.080 PII su un XLSX non devono produrre migliaia di controlli pesanti contemporaneamente: indice degli span, virtualizzazione/chunk rendering, memoization.
- Inference invalid: mostra “output non valido” con diagnostica disponibile, non 0 PII come falsa interpretazione di modello.

### 4.4 PII Inspector — progressive disclosure nel documento

Tabs secondarie: **Riepilogo | Mancate | Extra | Rilevate | Raw**. Default Riepilogo: 2–4 indicatori, cinque problemi principali e distribuzione sintetica per tipo.
- Filtri/prev-next sulla singola annotazione; confronta stato A vs B per lo stesso gold span/offset.
- FN = gold non identificata, TP = gold protetta/rilevata, FP = estrazione aggiuntiva non presente nel gold (NON automaticamente un dato non sensibile).
- Raw output/segment errors solo on-demand, mascherati di default, con status, versione, provenienza e indice segmento.
- Niente esportazione involontaria di testo PII in screen share, clipboard o log.

## 5. Contract dei dati — prerequisito fondamentale

Creare un adapter unico e testabile, ad esempio src/domain/benchmarkViewModel.js, per normalizzare i payload attuali:
- RunEvidence: run/suite ID, dataset, gold version, status complete/partial/legacy, provenance/hardware, qualità-latenza pair, cache verification, n campioni, human-reviewed se disponibile.
- ModelEvidence: metrics.micro, macro, macro_family, zero-leak, valid output count, FN/FP, tempi p50/p95; missing espressi come null e non come 0.
- DocumentEvidence: caseId, ext, semantic family, goldCount, per-model recall/leakage, TP/FP/FN, valid/error.
- SpanEvidence: id stabile basato su caseId/offset/type/model, start/end, etichetta e classe detected/missed/extra.
- ComparabilityEvidence: stessi dataset gold, contract/prompt, condizioni hardware, runtime e protocollo; se non comparabili, insights si astengono dal ranking.

Gap verificati nel middleware:
1. La paired latency esiste in /api/run, ma il quality manifest da solo non prova cache-off. Leggere e associare suite.json e campioni raw latency.
2. Una vecchia suite con cache hit non deve vincere la classifica velocità.
3. Gli score da gold non revisionato (human_reviewed=false) devono mostrare evidenza sperimentale, non certificazione.
4. Cross-run /api/overview mescola best-by-model: esporre sempre run source e segnalare differenze dataset/protocollo.
5. Validare offset rispetto al **medesimo testo canonico** usato dal modello. Se testo e span non coincidono, invalidare/omettere highlight invece di far apparire dati falsi.
6. Endpoint dettaglio documento lazy-loaded quando utile; non serializzare ogni testo e 1.080 span di tutti i file ad ogni polling.
7. Mai hardcodare dati presenti nei mockup nel runtime.

## 6. Design system e responsive

Tema scuro come default visivo, preservando Light/Auto già presenti.
- Palette superfici profonde, bordi sottili, accento blu per navigation, verde/rosso/ambra SOLO per esiti; icon/label oltre al colore.
- Gerarchia: heading 26–32px, KPI hero 28–36px, body >=14px, metadata >=12px.
- Token CSS e componenti V2 isolati con namespace (.rb2) / CSS modules; non ampliare styles.css globale.
- >=1280: sidebar 180–210px, due model card in riga, canvas dominante, confronto leggibile a 1440x900 senza scroll di tutta la vista principale.
- 1024–1279: sidebar comprimibile; Inspector chiudibile.
- 768–1023: navigazione compattata, drawer per inspector.
- <768: confronto modelli con toggle card/A-B, documento a **una colonna** con selezione modello, inspector bottom sheet; niente tabella enorme obbligatoria.
- Keyboard, visible focus, Esc per drawer, riduzione motion, contrasto AA, target touch >=44px.

## 7. Execution plan — lavoro parallelizzabile

### Milestone M0 — baseline e guardrail (deve precedere modifiche grosse)
- **UX-00** Snapshot della UI attuale sui breakpoints 1440x900, 1280x800, 390x844; fissare user journeys dai mockup.
- **UX-01** Fixtures sintetici *senza PII reali*: ultima suite Qwen, 4-modelli precedente, no-latency, partial, cached, invalid JSON, wrong offset, N modelli.
- **UX-02** Aggiungere test frontend unit/integration (Vitest + React Testing Library o equivalente) e smoke E2E Playwright/CI. package.json oggi ha solo dev/build/preview.
- **UX-03** Definire i criteri accessibilità, latenza render e sicurezza privacy.
**Gate M0:** build legacy verde, fixture e snapshot versionati.

### Milestone M1 — fondazioni in PARALLELO
**Workstream A: Data Evidence (ownership: server/adapter)**
- **DATA-01** Estrarre loader API da vite.config.js senza rompere /api/runs, /api/run, /api/overview.
- **DATA-02** Normalizzare qualità, macro per famiglia, latency source, comparabilità e cache-off dal suite.json.
- **DATA-03** Engine indici span, overlap e validazione offsets, inclusi 502 e output invalid.
- **DATA-04** Lazy data API/stream per dettagli documentali voluminosi, caching locale controllato.

**Workstream B: Design Shell (ownership: shell/theme/layout)**
- **DES-01** Token e componenti Button, Select, Segmented, MetricBar, Status, Tooltip, Drawer, Skeleton.
- **DES-02** Nuova shell/sidebar/topbar e responsive + route persistenti senza spostare logica nel main App.
- **DES-03** Stati empty, loading, invalid, comparison warning, AA/focus/keyboard.

A e B possono procedere indipendentemente dopo UX-01; fissare il ViewModel come contratto prima di costruire UI.

### Milestone M2 — pagine in PARALLELO
**Workstream C: Models**
- **MOD-01** ModelComparisonPage + switch Protezione/Velocità/Trade-off.
- **MOD-02** Card modello e summary algoritmico supportato da prove; niente “GDPR approved”.
- **MOD-03** Confronto 2 di N modelli e link a documenti; disclaimer n/quality evidence.

**Workstream D: Documents**
- **DOC-01** DocumentComparisonPage, scale comparabili, tabella delta e badge invalid.
- **DOC-02** Search/filter/sort + link alla vista singolo documento, stato run/model persistente.
- **DOC-03** Scroll/list virtualization e quality parity con raw evidence.

**Workstream E: Document Workspace + Inspector**
- **VIEW-01** Layout canvas 65–70% e inspector responsive chiudibile.
- **VIEW-02** Render strutturato (XLSX come tabella), singolo/affiancato, ancore e sync.
- **VIEW-03** Evidenziazione TP/FN/FP, privacy masking, selection bidirezionale.
- **VIEW-04** Tabs inspector, error navigator, raw disclosure mascherata.
- **VIEW-05** Performance su XLSX 1.080 PII con test di indexing/lazy render.

Dipendenze: C/D richiedono DATA-02 e DES-01; E richiede DATA-03 e DES-02. B e il rendering-base di E possono iniziare prima dell'integrazione dati.

### Milestone M3 — integrazione
- **INT-01** Collegare pagine alle route /client/* preservando deep link, ?run, back/forward, model picker.
- **INT-02** Rimuovere dalla navigazione primaria KPI duplicati e executive advisory con affermazioni GDPR non dimostrate; preservare advanced fino alla migrazione completa.
- **INT-03** Consistenza contatori per modello, documento e PII fra tre viste; single source of truth selectors.
- **INT-04** Privacy review: masking, print/export, debug log, local API e nessun network asset esterno.

### Milestone M4 — QA e rollout
- **QA-01** Unit: micro/macro, FN/FP, missing/invalid, partial, cache hit legacy, human-reviewed, cross-run, offsets.
- **QA-02** Browser E2E: scegli suite, switch criterio, seleziona modello, ordina documenti, apri XLSX, click FN -> naviga span, toggle A/B, back/forward, reveal/reset.
- **QA-03** Visual snapshots desktop/laptop/tablet/mobile, contrasto e keyboard test.
- **QA-04** Benchmark UI con 1.080 PII e 4+ modelli: nessun freeze percepibile, target interazione <200ms da misurare, payload API contenuto.
- **QA-05** Test 5 utenti sui task del §1; ritocchi UX basati sui risultati.
- **REL-01** Rollout progressive feature flag V2, vecchie viste advanced ancora disponibili; remove legacy in PR finale.
- **REL-02** README, FAQ, differenza testo canonico vs documento originale, limiti qualità e campione latenza.

## 8. Sequenza tecnica e PR

M0 -> **M1(A e B paralleli)** -> **M2(C/D/E paralleli dopo i rispettivi gate)** -> M3 -> M4.

| PR | Ambito | Gate di merge |
|---|---|---|
| PR-1 | Fixtures, test framework, ViewModel, design tokens, shell | Nessuna regressione API, demo shell responsive |
| PR-2 | Model Comparison V2 | Protezione/Velocità/Trade-off fedeli ai dati; nessuna cached latency |
| PR-3 | Document Comparison V2 | Matrice delta e fail states corretti, navigazione |
| PR-4 | Workspace e PII Inspector | Offset corretto, masking sicuro, demo 1.080 span |
| PR-5 | Routing/integrazione e advanced containment | Stesso run/modello in tutte le viste |
| PR-6 | A11y, responsive, perf, smoke e rollout | CI verde, UX user tasks superati |

Non assegnare App.jsx o styles.css a due stream contemporaneamente: shell owner B, merge dell'App nel ramo integrazione.

## 9. Definition of Done non negoziabile

1. Su suite Qwen cache-off 12/10: protezione visualizza 8/11 vs 6/11 zero-leak, distingue macro famiglia da micro. Velocità mostra misurazioni in secondi, con 15 campioni/modello, non i cached 2–10ms.
2. Latenza di run vecchi con cache non verificata non genera ranking; presenta un'etichetta “non confrontabile”.
3. Unified Overview che mischia benchmark non produce un “winner” come se le condizioni fossero identiche.
4. Nella matrice gli 11 documenti corrispondono ai caseId raw e i delta hanno segno corretto; invalid non diventa 0.
5. Click su una PII mancata trova l'offset giusto in entrambi i renderer. Offset incoerente -> warning, non highlight fuorviante.
6. Documento default masked e reveal solo volontario; cambio run/documento resetta il reveal. Nessun valore PII nei log nuovi.
7. Split view A/B è realmente navigabile con scroll/selection comune anche su file grandi.
8. UI mobile 390px senza overflow strutturale, pannello PII utilizzabile e tap target adeguati.
9. Le route correnti, il tema, gli strumenti advanced e il benchmark CLI Python continuano a funzionare senza modifiche.
10. Build, unit, integration e E2E verdi; screenshot prima/dopo; demo con due suite reali + fixture.

## 10. Non-obiettivi MVP e vincoli

- Pixel-perfect rendering dei PDF/Word/PowerPoint originali e coordinate fisiche: richiede file sorgenti e pipeline separata; non trattare il canonical Markdown come immagine del file reale.
- Certificazione GDPR, automatic approval alla produzione, winner assoluto, stima RAM non registrata.
- Cloud upload, telemetry, modifica gold dall'interfaccia.
- PII in chiaro nell'HTML condiviso, in report esportati o screenshot senza opt-in.
- Nuovi test modello richiesti solo per il redesign: la UI deve usare i risultati già salvati.

**Decisione:** SPA React/Vite esistente + ViewModel unico dell'evidenza + tre route principali + quattro stati UX (ultimo: inspector contestuale) + dark-first + progressive disclosure. Lavoro modulare e verificabile in PR indipendenti.
