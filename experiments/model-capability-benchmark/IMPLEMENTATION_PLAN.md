# Model Capability Benchmark — Implementation Plan

## 1. Obiettivo

Creare nel repository `experiments` un nuovo filone, `model-capability-benchmark`, per confrontare modelli locali e remoti/API su dataset differenti e task differenti, riutilizzando quanto più possibile l'infrastruttura già realizzata in `jev-vs-llm`.

L'obiettivo non è creare una seconda implementazione parallela del benchmark, ma evolvere il repository verso una piccola piattaforma sperimentale condivisa:

```text
                         benchmark-core
                              |
              +---------------+----------------+
              |                                |
         jev-vs-llm                 model-capability-benchmark
              |                                |
     bounded decisions                  generic LLM tasks
```

Il nuovo benchmark deve rendere indipendenti:

1. modello;
2. runtime/provider;
3. task;
4. dataset;
5. prompt/protocollo di inferenza;
6. evaluator/metriche;
7. profilo di esecuzione;
8. reporting.

## 2. Principi architetturali

### P1 — No duplication

Il nuovo filone non deve copiare `jev_bench`, i provider, il reporting o l'orchestrazione locale. Le parti realmente generiche vanno estratte in un core condiviso.

### P2 — Migrazione incrementale

`jev-vs-llm` deve continuare a funzionare durante tutta la migrazione. Ogni estrazione dal codice esistente deve essere coperta da characterization/regression test prima di modificare l'implementazione.

### P3 — Configuration first

Modelli, suite, task, dataset, profili, generation parameters e metriche devono essere dichiarati tramite configurazione o registry. Il runner non deve contenere catene di `if model == ...` o `if dataset == ...` per casi specifici.

### P4 — Provider != model != task

Un modello è un'entità valutata. Il provider/runtime descrive come viene invocato. Il task descrive cosa gli viene chiesto. Il dataset fornisce i casi. L'evaluator decide come misurare la risposta.

### P5 — Local e cloud sono deployment mode

"Local vs cloud" non deve diventare una specializzazione del runner. Deve essere una proprietà del model/runtime registry.

### P6 — Raw evidence first

Ogni run deve conservare output grezzi, output normalizzati, metriche, latenza, token usage, costo noto/stimato, configurazione effettiva e manifest riproducibile.

### P7 — Nessun overall score opaco

Il reporting deve privilegiare una capability matrix e metriche per task. Un eventuale aggregato futuro deve essere esplicito, configurabile e non sostituire i dati primari.

---

## 3. Stato attuale da riutilizzare

`experiments/jev-vs-llm` contiene già componenti utili:

- provider abstraction;
- Korgis runtime/lifecycle management;
- provider OpenAI-compatible;
- provider OpenAI;
- CLM provider;
- MiniCPM provider/API integration;
- model registry locale;
- dataset cache e preparazione di BANKING77 / CLINC150;
- seed e run manifest;
- token/cost/latency telemetry;
- matrix orchestration;
- progress UI;
- persistenza CSV;
- HTML reporting;
- metriche classification/calibration;
- smoke/public profiles.

Sono invece Jev-specific o bounded-decision-specific e non vanno promossi direttamente a core generico:

- `DecisionProvider`;
- `QuestionSpec`;
- semantiche `choice`, `noul`, `score`;
- routing/calibration/workflow/agent specifici;
- policy deterministic workflow;
- JevProvider;
- assunzioni su `answers[]` e relativo schema.

---

## 4. Target structure

```text
experiments/
├── packages/
│   └── benchmark-core/
│       ├── pyproject.toml
│       ├── src/benchmark_core/
│       │   ├── contracts/
│       │   ├── providers/
│       │   ├── runtimes/
│       │   ├── registry/
│       │   ├── datasets/
│       │   ├── tasks/
│       │   ├── evaluators/
│       │   ├── runner/
│       │   ├── persistence/
│       │   ├── reporting/
│       │   └── manifests/
│       └── tests/
│
├── experiments/
│   ├── jev-vs-llm/
│   │   ├── suite.yaml
│   │   ├── ...
│   │   └── src/...
│   │
│   ├── model-capability-benchmark/
│   │   ├── README.md
│   │   ├── IMPLEMENTATION_PLAN.md
│   │   ├── models.yaml
│   │   ├── suite.yaml
│   │   ├── profiles/
│   │   ├── tasks/
│   │   ├── prompts/
│   │   ├── results/
│   │   └── scripts/
│   │
│   └── redactguard-local-anonymization/
```

La struttura esatta potrà essere adattata durante l'estrazione, ma la dipendenza deve restare unidirezionale:

```text
experiment suites -> benchmark-core
benchmark-core -X-> experiment suites
```

---

# 5. Workstream

## MCB-0 — Baseline e characterization tests ✅ COMPLETE

### Obiettivo

Congelare il comportamento osservabile attuale di `jev-vs-llm` prima della refactor.

### Attività

- identificare gli entrypoint correnti;
- aggiungere test di regressione sul runner smoke;
- aggiungere test su provider result normalization;
- aggiungere test su tagging e manifest;
- aggiungere test su CSV/report schema;
- aggiungere fixture deterministiche che non richiedano API o modello reale;
- salvare una baseline golden minima per:
  - routing;
  - calibration;
  - workflow;
  - agent;
  - scaling;
- verificare che BANKING77/CLINC150 mantengano sampling e seed riproducibili.

### Definition of Done

- il comportamento essenziale di `jev-vs-llm` è protetto da test;
- i test core non richiedono credenziali esterne;
- esiste almeno un smoke end-to-end con fake provider;
- sono documentati gli output contract da non rompere durante MCB-1/2.

---

## MCB-1 — Definizione dei contratti generici ✅ COMPLETE

### Obiettivo

Introdurre primitive che non assumano bounded decisions.

### Contratti iniziali

```python
InferenceRequest
InferenceResult
ModelSpec
ProviderSpec
RuntimeSpec
RunContext
Sample
TaskResult
MetricResult
RunManifest
```

### Requisiti

`InferenceRequest` deve poter rappresentare almeno:

- messages/input;
- system prompt opzionale;
- response schema opzionale;
- generation params;
- task metadata.

`InferenceResult` deve rappresentare almeno:

- raw output;
- normalized output opzionale;
- latency;
- token usage;
- cost;
- validity;
- error;
- provider/runtime metadata.

### Compatibilità Jev

Creare un adapter:

```text
DecisionTask / DecisionProvider compatibility layer
                      ↓
              generic inference core
```

Non eliminare ancora `DecisionProvider`.

### Definition of Done

- i contratti generici non importano `jev_bench`;
- un fake provider può soddisfare `InferenceProvider`;
- un adapter consente al bounded-decision stack di continuare a funzionare.

---

## MCB-2 — Estrazione di `benchmark-core` ✅ COMPLETE

### Obiettivo

Spostare nel package condiviso solo componenti già dimostrati generici.

### Prima estrazione

MCB-2A ha estratto manifest, run identity/tagging e persistence CSV. MCB-2B ha aggiunto config loading, matrix-arm execution e summary primitives. MCB-2C ha aggiunto pricing hooks, reproducibility/fingerprinting e i record generici raw/evaluation/aggregate. MCB-2D ha completato l'estrazione con transport policy, JSON HTTP transport, error normalization e OpenAI-compatible client construction. MCB-2 è quindi chiuso.

- manifest; ✅ MCB-2A
- run identity;
- common telemetry; ✅ contract condiviso, wiring progressivo
- persistence primitives; ✅ MCB-2A
- common report data model; ✅ generic evidence/aggregate records MCB-2C
- common model/provider config loading; ✅ loader/config primitives MCB-2B, typed registry in MCB-3
- utilities per seed/reproducibility; ✅ MCB-2C
- generic provider protocol; ✅ MCB-1
- generic runner primitives. ✅ MCB-2B

### Seconda estrazione

Dopo regression test:

- OpenAI-compatible transport; ✅ MCB-2D
- generic OpenAI transport/client construction; ✅ MCB-2D
- runtime-independent error normalization; ✅ MCB-2D
- common retry/timeout policy; ✅ MCB-2D
- common cost hooks. ✅ MCB-2C

### Da non estrarre prematuramente

- `QuestionSpec`;
- decision parsing;
- Jev semantics;
- workflow actions;
- Korgis process orchestration se rimane troppo specifica al runtime locale.

Korgis può vivere inizialmente come runtime adapter condiviso senza forzare altri provider nello stesso lifecycle.

### Definition of Done

- `jev-vs-llm` dipende dal nuovo package;
- tutti i regression test di MCB-0 restano verdi;
- non esistono copie parallele dei componenti estratti.

---

## MCB-3 — Model e runtime registry unificato ✅ COMPLETE

### Obiettivo

Rendere confrontabili modelli locali e remoti attraverso un registry dichiarativo.

### Schema concettuale

```yaml
models:
  example-local:
    model_id: vendor/model
    runtime: korgis-local
    deployment: local
    artifact:
      format: gguf
      quantization: Q4_K_M

  example-api:
    model_id: provider/model
    runtime: provider-api
    deployment: api
```

Separare le informazioni del modello dalle informazioni del runtime:

```yaml
runtimes:
  korgis-local:
    type: korgis
    base_url_env: KORGIS_BASE_URL

  provider-api:
    type: openai-compatible
    base_url_env: PROVIDER_BASE_URL
    api_key_env: PROVIDER_API_KEY
```

### Vincoli

- nessuna API key nel registry;
- nessun path locale obbligatorio committato come configurazione universale;
- override tramite environment/config locale;
- possibilità di filtrare per tag, deployment, famiglia, dimensione e quantizzazione.

### Definition of Done

- [x] lo stesso resolver/CLI risolve almeno un modello Korgis e un modello API;
- [x] runtime, provider e modello sono entità separate;
- [x] configurazioni mancanti falliscono in preflight, prima di iniziare il benchmark;
- [x] il registry riusa anche le ModelCapabilities multimodali del core condiviso;
- [x] nessun secret o path macchina è committato nel nuovo registry.

---

## MCB-4 — Task registry e plugin protocol ✅ COMPLETE

### Obiettivo

Eliminare la crescita lineare di `if/elif` nel runner.

### Interfaccia concettuale

```python
class BenchmarkTask:
    def build_request(sample, context): ...
    def evaluate(sample, inference, context): ...
```

Ogni task dichiara inoltre:

- task id/version;
- capabilities;
- compatible datasets;
- evaluator;
- prompt/version;
- required model capabilities;
- metric schema.

### Registry

```text
task_id
  ↓
TaskSpec
  ↓
loader + request builder + evaluator
```

Il runner conosce il registry, non i singoli task. Il caricamento dataset è intenzionalmente escluso dal protocollo task e appartiene a MCB-5.

### Definition of Done

- aggiungere un nuovo task non richiede modificare il loop principale;
- task e evaluator possono essere testati indipendentemente dal provider;
- task version e prompt version finiscono nel manifest.

---

## MCB-5 — Dataset registry e dataset adapters ✅ COMPLETE

### Obiettivo

Separare definitivamente dataset e task.

### Primo set

Riutilizzare ciò che esiste:

- BANKING77;
- CLINC150.

Aggiungere progressivamente dataset per:

- QA con answerability;
- mathematical reasoning;
- structured extraction/output;
- instruction following;
- summarization.

### Dataset adapter contract

Ogni adapter deve dichiarare:

- dataset id;
- version/revision;
- source;
- license/provenance metadata;
- split;
- deterministic sampling;
- normalization;
- sample schema;
- cache behavior;
- checksum/revision quando disponibile.

### Profili

I profili non devono essere hardcoded in Python.

Esempio:

```yaml
profiles:
  smoke:
    max_cases: 20
  budget:
    max_cases: 100
  standard:
    max_cases: 1000
  full:
    max_cases: null
```

I singoli task possono fare override dichiarativi.

### Definition of Done

- [x] BANKING77 passa attraverso il nuovo dataset registry;
- [x] sampling deterministico e class-balanced verificato;
- [x] CLINC150 OOS passa da un adapter versionato e configurato;
- [x] source checksums e selection fingerprint sono persistibili come provenance;
- [x] profili smoke/budget/standard/full sono configurazione;
- [x] aggiungere un dataset non richiede modificare il runner.

---

## MCB-6 — Prima capability suite ✅ COMPLETE

### Obiettivo

Creare il nuovo filone `model-capability-benchmark` con una matrice piccola ma utile.

### Capability iniziali

#### A. Intent classification

Dataset iniziale: BANKING77.

Metriche:

- accuracy;
- macro-F1;
- invalid output rate;
- latency;
- token usage;
- cost quando disponibile.

#### B. OOS / calibration

Dataset: BANKING77 + CLINC150.

Metriche:

- in-scope accuracy;
- OOS detection;
- ECE;
- Brier score;
- coverage/reliability data.

#### C. QA + abstention

Dataset da selezionare/versionare esplicitamente.

Metriche:

- exact match;
- token/span F1 dove applicabile;
- answerability/abstention;
- invalid output.

#### D. Mathematical reasoning

Dataset da selezionare/versionare esplicitamente.

Metriche:

- final-answer accuracy;
- parse validity;
- latency/tokens/cost.

Il benchmark non deve valutare chain-of-thought privata; deve valutare l'output osservabile richiesto dal task.

#### E. Structured output

Suite controllata e/o dataset pubblico adeguato.

Metriche:

- schema-valid rate;
- exact field accuracy;
- partial field accuracy;
- hallucinated fields;
- latency/tokens.

### Estensioni successive

- summarization;
- information extraction;
- tool/function selection;
- tool argument generation;
- multi-label classification;
- long-context retrieval/QA;
- code generation;
- multimodal task quando supportato dai runtime.

### Definition of Done

- [x] 5 capability differenti: classification, OOS/calibration, structured output, QA/abstention, reasoning;
- [x] almeno 3 dataset/task family indipendenti;
- [x] local e API model attraversano lo stesso suite planner e la stessa matrice dichiarativa;
- [x] OOS/calibration compone BANKING77 + CLINC150 tramite capability context binding;
- [x] structured output usa validazione JSON Schema reale;
- [x] QA e reasoning usano dataset controlled versionati;
- [x] l'esecuzione multi-model/multi-task con un solo comando è implementata in MCB-7.

---

## MCB-7 — Unified matrix runner ✅ IMPLEMENTED

### Obiettivo

Fornire un unico entrypoint dichiarativo.

### UX target

```bash
uv run model-bench run \
  --suite capability-core \
  --models qwen-local-small,qwen-local-large,cloud-model \
  --profile budget
```

Supportare inoltre:

```bash
uv run model-bench models
uv run model-bench tasks
uv run model-bench datasets
uv run model-bench validate-config
```

### Loop target

```text
resolve suite
   ↓
resolve model × task matrix
   ↓
preflight runtimes/datasets
   ↓
for each model
   activate runtime/model if needed
   for each task
      load deterministic sample set
      build request
      infer
      evaluate
      persist evidence immediately
   release model if needed
   ↓
aggregate/report
```

### Resilience

- persistence incrementale, non solo a fine run;
- resume support tramite run manifest/case identity;
- failed case separato da wrong answer;
- provider/runtime failure separato da evaluator failure;
- interruzione di un modello non deve perdere i risultati precedenti.

### Definition of Done

- [x] local e API model passano dallo stesso matrix runner;
- [x] risultati sono resumable tramite semantic case identity e attempt journal;
- [x] gli errori/failure stage sono separati da wrong/invalid answers;
- [x] non esistono branch specifici per model family nel loop principale;
- [x] raw inference, evaluation, aggregates, events e manifest sono persistiti;
- [x] provider OpenAI-compatible, OpenAI Responses e lifecycle Korgis sono registry-driven;
- [x] fake E2E multi-model, resume, retry, provider/runtime e CLI sono coperti in CI;
- [ ] controlled E2E con Korgis reale + API reale: pending environmental validation, non per-commit CI.

---

## MCB-8 — Reporting e capability matrix ✅ COMPLETE

### Obiettivo

Evolvere il reporting esistente da report Jev a confronto multidimensionale.

### Vista principale

```text
                 Model A   Model B   Model C
classification
calibration
QA
reasoning
structured output
```

### Dimensioni secondarie

Per ogni task/modello:

- primary quality metric;
- validity;
- latency p50/p95;
- input/output tokens;
- estimated API cost;
- throughput quando disponibile;
- model size;
- quantization;
- local/cloud deployment.

### Local resource metrics

Non confondere `API cost = 0` con `runtime cost = 0`.

Per i modelli locali mantenere campi distinti per:

- model artifact size;
- peak RAM/VRAM se misurabile;
- tokens/s;
- startup/model-switch latency;
- hardware identity quando utile.

### Definition of Done

- [x] confronto leggibile capability/task × modello;
- [x] drill-down ai singoli casi e attempt esatti;
- [x] raw/evaluation evidence collegata alle aggregazioni tramite report index;
- [x] nessun ranking unico obbligatorio;
- [x] HTML standalone e JSON machine-readable;
- [x] rendering artifact-only senza provider/runtime;
- [x] API cost unknown resta null e local provider fee 0 non implica runtime cost 0.

---

## MCB-9 — Migrazione di `jev-vs-llm` al core definitivo ✅ COMPLETE

### Obiettivo

Rimuovere duplicazioni transitorie create durante la migrazione.

### Attività

- Jev task adapters su benchmark-core;
- riuso del dataset registry condiviso;
- riuso del model/runtime registry dove sensato;
- riuso della persistence/report telemetry;
- mantenere evaluator e decision semantics nella suite Jev;
- deprecare entrypoint duplicati solo dopo compatibilità verificata.

### Definition of Done

- [x] un solo implementation path per telemetry/manifests/persistence condivisi;
- [x] dataset source/parsing e model/runtime registry consolidati nel core condiviso;
- [x] vecchi comandi Jev mantenuti e migration path locale documentato;
- [x] generic Jev task adapter disponibile senza spostare bounded-decision semantics nel core;
- [x] risultati Jev pre/post migration confermati dai regression fixtures sulla HEAD finale;
- [x] gate cumulativi verdi sulla HEAD finale.

---

## MCB-10 — Vertical benchmark hardening & efficiency ✅ IMPLEMENTED / VALIDATION PENDING

### Obiettivo

Rendere la suite decision-grade e verticale per task senza aumentare il benchmark a migliaia di casi, con guardrail espliciti su tempo locale e costo API.

### Implementato

- benchmark tiers capability-specific: smoke/core/extended;
- core v2 da 468 casi/modello:
  - 154 intent classification;
  - 154 OOS/calibration;
  - 60 structured output;
  - 60 QA/abstention;
  - 40 reasoning;
- selezione deterministica stratificata tramite family/difficulty/challenge_type;
- dataset controlled v2 versionati;
- cache dataset capability/profile/seed-aware;
- budget aggregato core target 28 min, hard 45 min locale;
- API budget core target USD 0.45, hard USD 1.00;
- comando plan senza inferenza;
- comando estimate con pilot reale e proiezione runtime/costo;
- pricing snapshot versionato usato da estimate e full run;
- costo sconosciuto preservato come null quando il modello non ha pricing dichiarato;
- paired bootstrap CI + McNemar su stessi sample ID;
- practical delta per capability;
- reporting per family e difficulty;
- structured-output primary metric semantica exact_match;
- QA primary metric qa_correct che include i casi unanswerable;
- comparison metric OOS esplicita oos_correct;
- version bump degli evaluator modificati e suite v2.

### Definition of Done

- [x] cardinalità core differenziata per task;
- [x] stessa selezione deterministica per tutti i modelli confrontati;
- [x] family/difficulty persistite nell'evidence;
- [x] plan mostra cardinalità e guardrail prima della run;
- [x] estimate usa pochi casi e proietta runtime/costo senza eseguire il benchmark completo;
- [x] pricing snapshot è checksumato nel manifest e arricchisce anche la full run;
- [x] confronti paired ricostruibili offline dagli artifact;
- [x] metriche primarie structured/QA coprono qualità semantica reale;
- [x] report mantiene neutralità e non produce ranking globale;
- [ ] esecuzione dei gate locali ruff/pytest sulla HEAD del branch;
- [ ] controlled E2E Korgis + API sul profilo core.

### Enhancement successivi

- repeated performance microbenchmark separato dalla quality run;
- RAM/VRAM, throughput e startup/switch telemetry;
- OOS near-domain v2 curato;
- modalità parity vs native per i meccanismi di structured generation.

Vedi `MCB_10_VERTICAL_BENCHMARK_HARDENING.md`.

---

## MCB-11 — Benchmark observability, results explorer & shareable insights 🟡 IN PROGRESS

### Obiettivo

Separare in modo netto source-of-truth, analytics e presentation:

```text
immutable run evidence
        ↓
typed observability + signatures
        ↓
DuckDB projector/read model
        ↓
typed dashboard payloads
        ↓
Results UI / Runs UI / Share snapshots
```

### Principi chiave

- i JSONL/manifest dei run restano immutabili e ricostruibili;
- DuckDB è una projection cancellabile e rebuildable, non il source of truth;
- il browser riceve payload JSON tipizzati e non ricalcola statistiche;
- "latest" significa latest valid completed **comparable** result;
- qualità e performance hanno regole di comparabilità distinte;
- risultati partial/failed restano navigabili ma non sostituiscono il CURRENT;
- storico e benchmark lineage restano preservati;
- nessun overall score opaco;
- share/LinkedIn usa snapshot immutabili, non lo stato live della dashboard.

### Workstream

- MCB-11A typed observability envelope;
- MCB-11B model/benchmark/execution signatures;
- MCB-11C run lifecycle + canonical latest policy;
- MCB-11D DuckDB analytics projector;
- MCB-11E typed dashboard export;
- MCB-11F React/Vite dashboard foundation + URL routing;
- MCB-11G Overview capability matrix;
- MCB-11H Capability detail;
- MCB-11I disagreement/case explorer;
- MCB-11J model profile + benchmark history;
- MCB-11K Runs/timeline/failure explorer;
- MCB-11L local resource telemetry contract;
- MCB-11M immutable share snapshots;
- MCB-11N LinkedIn PNG/PDF renderer.

### Primo vertical slice

Validare end-to-end con:

- 2 modelli;
- structured-output;
- 60 casi paired / 6 famiglie;
- 2 run storici completati;
- 1 run più recente partial;
- CURRENT selection;
- overview;
- capability detail;
- disagreement explorer;
- 1 share snapshot + 1 LinkedIn card.

Questo slice deve dimostrare che una run partial più recente non sostituisce l'ultimo risultato valido e che una modifica a evaluator/dataset selection apre una nuova benchmark lineage.

### Definition of Done

- [x] event lifecycle tipizzato e versionato;
- [x] signature deterministiche con golden tests;
- [x] latest comparable policy coperta da test;
- [x] DuckDB rebuild == incremental projection;
- [ ] Overview/Capability/Model/Run routes deep-linkable; Overview/Capability completate nel primo slice;
- [x] disagreement explorer basato su exact paired sample IDs;
- [ ] history non unisce benchmark lineage incompatibili;
- [ ] resource telemetry nullable e execution-signature-aware;
- [x] share snapshot immutabile;
- [ ] card/carousel LinkedIn renderizzabili deterministicamente; preview card implementata, PNG/PDF renderer pending;
- [ ] visual regression per viste/card principali;
- [ ] gate locali verdi senza dipendenza da GitHub Actions.

Vedi `MCB_11_OBSERVABILITY_RESULTS_EXPLORER.md`.

---

# 6. Dipendenze

```text
MCB-0 Baseline tests
       |
       v
MCB-1 Generic contracts
       |
       v
MCB-2 benchmark-core extraction
       |
       +-------------------+
       |                   |
       v                   v
MCB-3 model/runtime     MCB-4 task registry
registry                   |
       |                   v
       |              MCB-5 dataset registry
       |                   |
       +---------+---------+
                 |
                 v
          MCB-6 capability suite
                 |
                 v
          MCB-7 matrix runner
                 |
                 v
          MCB-8 reporting
                 |
                 v
          MCB-9 Jev cleanup
                 |
                 v
          MCB-10 vertical hardening
```

MCB-3 e MCB-4 possono procedere in parallelo dopo la stabilizzazione dei contratti core. MCB-5 può procedere in parallelo alla parte finale di MCB-4 una volta fissati Sample e Task contracts.

---

# 7. Test strategy

## Unit

- config parsing;
- registry resolution;
- request builders;
- output parsers;
- evaluator metrics;
- sampling;
- normalization;
- manifest generation.

## Contract

Ogni provider/runtime deve superare gli stessi contract test:

- successful inference;
- invalid response;
- timeout;
- authentication/config error;
- token metadata absent/present;
- structured response support dichiarato correttamente.

## Dataset

- deterministic selection;
- schema validation;
- expected labels;
- no silent duplicate IDs;
- version/source metadata.

## Integration

- fake provider + real task + real evaluator;
- local OpenAI-compatible fake endpoint;
- manifest + persistence + report pipeline.

## Controlled E2E

Da eseguire solo dopo che la feature è assemblata:

1. un modello Korgis reale;
2. un modello API reale;
3. almeno due task;
4. stesso seed/profile;
5. report finale comparativo.

Gli E2E costosi/non deterministici non devono partire per ogni commit intermedio.

---

# 8. Config validation e anti-hardcoding rules

Il nuovo filone deve introdurre check automatici che impediscano configurazioni importanti disperse nel codice.

Devono stare in config/registry almeno:

- model IDs;
- endpoint reference tramite env;
- dataset selection;
- dataset revision;
- sample limits;
- generation limits;
- temperature;
- seed/default profile;
- timeout/retry policy configurabile;
- output paths;
- metric selection;
- prompt/template references.

Sono accettabili nel codice solo default tecnici innocui e invarianti di protocollo. Ogni default operativo deve essere visibile e sovrascrivibile.

Aggiungere test/static checks dove ragionevole per prevenire regressioni di hardcoding.

---

# 9. Run manifest minimo

Ogni run deve rendere possibile rispondere a:

> Esattamente quale modello, runtime, prompt, dataset, subset, codice e configurazione hanno prodotto questo risultato?

Campi minimi:

```text
run_id
run_group
git_commit
benchmark_core_version
suite_id/version
task_id/version
prompt_id/version
dataset_id/revision/split
sample_profile
sample_ids or deterministic selection fingerprint
model_key
model_id
model metadata
runtime key/type
deployment
quantization/artifact metadata
generation parameters
seed
start/end timestamps
provider identity where available
hardware identity where relevant
pricing snapshot/version
```

Le credenziali non devono mai essere persistite.

---

# 10. Result schema

Il core deve distinguere chiaramente tre livelli:

## Raw inference record

Una riga/record per sample × model × task:

- input/sample reference;
- raw output;
- normalized output;
- latency;
- tokens;
- cost;
- validity;
- error type;
- runtime metadata.

## Evaluation record

- expected;
- prediction;
- per-case metric values;
- evaluator version;
- parsing/validation outcome.

## Aggregate record

- model;
- task;
- dataset/profile;
- metric;
- value;
- sample count;
- failure count.

Questo evita di appiattire task diversi nel vecchio schema `correct/valid`.

---

# 11. Primo vertical slice consigliato

Il primo obiettivo implementativo dopo MCB-0/1/2 deve essere volutamente piccolo:

```text
Models
  ├─ 1 Korgis local model
  └─ 1 API model

Tasks
  ├─ BANKING77 classification
  └─ structured-output controlled suite

Profiles
  ├─ smoke
  └─ budget

Outputs
  ├─ raw records
  ├─ manifest
  └─ minimal comparative report
```

Questo vertical slice deve validare l'architettura generica prima di aggiungere altri dataset.

---

# 12. Sequenza di delivery

### Foundation

- [x] MCB-0 characterization tests
- [x] MCB-1 generic contracts
- [x] MCB-2 benchmark-core extraction

### Extensibility

- [x] MCB-3 model/runtime registry
- [x] MCB-4 task registry
- [x] MCB-5 dataset registry

### First product slice

- [x] BANKING77 via generic task
- [x] structured-output task
- [x] one local + one API runtime
- [x] generic matrix runner
- [x] raw evidence + manifest
- [x] minimal comparative report

### Capability expansion

- [x] calibration/OOS
- [x] QA + abstention
- [x] reasoning
- [ ] summarization
- [ ] extraction
- [ ] tool/function calling

### Consolidation

- [ ] capability matrix dashboard
- [x] vertical core tiers + deterministic stratification
- [x] pre-run plan + pilot estimate
- [x] paired statistics + vertical breakdown reporting
- [x] resume/failure hardening
- [ ] local resource telemetry
- [x] Jev migration cleanup
- [ ] documentation/tutorial for adding model/task/dataset/provider

---

# 13. Success criteria

Il workstream è concluso quando:

1. un nuovo modello può essere aggiunto principalmente tramite registry/config;
2. un nuovo dataset può essere aggiunto tramite adapter/registry senza toccare il matrix runner;
3. un nuovo task può essere aggiunto come plugin senza modificare il loop di esecuzione;
4. un modello locale e uno API possono essere confrontati sullo stesso task;
5. `jev-vs-llm` continua a funzionare sul core condiviso;
6. ogni risultato è riproducibile tramite manifest;
7. il report confronta capability diverse senza ridurle obbligatoriamente a un singolo score;
8. configurazione operativa e benchmark parameters non sono hardcoded nel codice;
9. smoke e unit/contract tests sono separati dagli E2E costosi;
10. raw evidence, evaluation e aggregate metrics restano accessibili separatamente.

---

# 14. Stato finale e prossime validazioni

Il workstream architetturale **MCB-0…10 è implementato**: contratti, core condiviso,
registry, task/dataset plugin, capability suite, unified runner, reporting e migrazione Jev
sono consolidati e coperti dai gate automatici.

La prossima attività non è un nuovo refactor strutturale. È la **validazione ambientale
controlled E2E** già documentata in `MCB_7_UNIFIED_RUNNER.md`:

- eseguire lo stesso slice su un modello Korgis reale e un modello API reale;
- conservare evidence, manifest e report della run;
- confrontare validità, qualità, latenza, token e costo osservato;
- verificare resume/failure handling anche su runtime reale.

Enhancement successivi, non blocker del core MCB-0…9:

- local resource telemetry (RAM/VRAM, throughput, startup/switch latency quando misurabile);
- tutorial operativo per aggiungere model/task/dataset/provider;
- nuove capability/dataset in base agli esperimenti editoriali.


---

## MCB-12 — Efficiency telemetry & share renderer 🔜 PLANNED

### Obiettivo

Completare gli enrichment non bloccanti estratti da MCB-11:

- telemetria CPU/RAM/runtime per modelli locali;
- comparabilità delle metriche di efficienza vincolata all'execution signature;
- pannelli efficiency in Model, Run e Compare;
- renderer deterministico degli share snapshot in PNG/PDF;
- carousel LinkedIn e visual regression.

Il contratto dettagliato è in `MCB_12_EFFICIENCY_TELEMETRY_SHARE_RENDERER.md`.

### Definition of Done

- resource telemetry opzionale, versionata e non-fatal;
- nessuna metrica hardware inventata quando il runtime non la espone;
- performance/resource comparison bloccata quando le execution signature non sono compatibili;
- rendering da snapshot immutabile senza provider call;
- output PNG e PDF con provenance;
- visual regression e gate dedicati.

---

## MCB-13 — Premium decision dashboard UX/UI ✅ CORE COMPLETE

### Obiettivo

Evolvere la dashboard MCB da benchmark explorer tecnico a prodotto decisionale premium, mantenendo immutabili i contratti di evidence/comparability costruiti in MCB-11/12.

La gerarchia target è:

```text
DECIDE → UNDERSTAND → DIAGNOSE → AUDIT
```

Il primo vertical slice è la nuova Overview:

- KPI decisionali;
- benchmark quality leaderboard con policy esplicita/versionata;
- observed quality × latency;
- quality × known provider cost;
- performance by dataset;
- dettaglio human-readable del modello selezionato;
- metodologia/provenance in progressive disclosure.

Il workstream include inoltre:

- dataset come drill-down first-class;
- premium Model detail;
- premium Capability detail;
- Compare workspace per 2–4 modelli;
- refactor del frontend monolitico;
- proiezioni P50/P95, cost/1k cases, dataset summary ed execution environment;
- semantic guardrails per observed vs comparable efficiency;
- visual regression e real-Chrome screenshot gate.

Il contratto dettagliato è in `MCB_13_PREMIUM_DECISION_DASHBOARD.md`.

### Definition of Done

- decision-first Overview validata su evidence reale;
- overall quality disponibile solo tramite policy esplicita/versionata;
- local provider cost mai rappresentato come zero;
- trade-off cross-environment marcati come observed;
- dataset drill-down disponibile;
- runtime/hardware locale leggibile senza dover interpretare signature hash;
- App.tsx decomposto in pagine/componenti condivisi;
- visual regression delle viste premium principali.

