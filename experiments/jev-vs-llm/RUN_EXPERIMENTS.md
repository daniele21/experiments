# Guida all'Esecuzione dei Benchmark con Modelli Locali

Questo documento raccoglie tutti i comandi pronti all'uso per eseguire i benchmark di `jev-vs-llm` sui 4 modelli selezionati in locale tramite l'orchestratore autonomo di Korgis.

---

## 1. I 4 Modelli Locali Selezionati

Tutti i modelli sono configurati in [`benchmark-models.yaml`](./benchmark-models.yaml) e puntano agli artifact GGUF scaricati in LM Studio:

| Identificativo Chiave | Modello Base | Quantizzazione | Dimensione | Uso Consigliato |
|---|---|---|---|---|
| **`nemotron-nano-4b`** | NVIDIA Nemotron-3 Nano 4B | `Q4_K_M` | 2.5 GB | Baseline veloce, ottimo bilanciamento velocità/accuratezza |
| **`nemotron-nano-4b-q8`** | NVIDIA Nemotron-3 Nano 4B | `Q8_0` | 4.3 GB | Massima fedeltà e calibrazione sulla classe 4B |
| **`qwen3.5-9b-q4km`** | Qwen 3.5 9B | `Q4_K_M` | 5.6 GB | Modello ad alte prestazioni per compiti multi-classe complessi |
| **`qwen3.5-2b-q4km`** | Qwen 3.5 2B | `Q4_K_M` | 1.2 GB | Modello ultraleggero compatto |

> [!NOTE]
> `qwen3.5-0.8b-q4km` rimane registrato nel file di configurazione per test di regressione, ma è escluso dalle sequenze di valutazione standard.

---

## 2. Panoramica Dettagliata degli Esperimenti

La suite include 5 tipologie di esperimenti per valutare sia la precisione semantica del modello sia la sua tenuta architetturale in contesti decisionali strutturati.

### Tabella di Riferimento per il Parametro `--experiments`

| Chiave `--experiments` | ID Esperimento | Cosa valuta | Metriche Primarie | Tier `smoke` | Tier `public` |
|---|---|---|---|:---:|:---:|
| **`routing`** | `01-routing` | Classificazione multi-classe dell'intento (routing ticket) | Accuratezza, Macro-F1, Validità JSON, Latenza | ✅ *(24 casi)* | ✅ *(77 classi reali)* |
| **`calibration`** | `02-calibration` | Calibrazione confidenza e scarto richieste fuori dominio (OOS) | ECE, Brier Score, Reliability Curve, Coverage | ✅ *(24 casi)* | ✅ *(BANKING77 + CLINC150)* |
| **`scaling`** | `03-scaling` | Stress-test con 1 → 32 decisioni parallele in una sola chiamata | Validità schema, Latenza p50/p95, Token ratio | ✅ *(1,2,4,8,16,32 Q)* | ❌ *(solo sintetico)* |
| **`workflow`** | `04-workflow` | Policy aziendale ibrida: modello fuzzy + regole Python | Accuratezza intermedia, Azione finale corretta | ✅ *(note spese)* | ❌ *(solo sintetico)* |
| **`agent`** | `05-agent` | Agente decisionale di supporto clienti con policy di escalation | Decisione intermedia, Azione di escalation/handoff | ✅ *(supporto escalation)* | ❌ *(solo sintetico)* |
| **`all`** | *Speciale* | Lancia automaticamente tutti gli esperimenti disponibili per il tier | Tutte le metriche aggregate | ✅ *(tutti e 5)* | ✅ *(`routing` + `calibration`)* |

---

### Perché alcuni esperimenti sono solo su dataset sintetico/controllato?

- **`01 Routing` e `02 Calibration` (Dataset Pubblici Reali)**:  
  Sono compiti canonici di NLP (Text Classification e Out-Of-Scope Detection). Per questi compiti la comunità scientifica ha creato dataset standard annotati da esseri umani:
  - **BANKING77** *(PolyAI)*: 13.083 query bancarie reali umane suddivise su 77 intent.
  - **CLINC150** *(Larson et al.)*: 150 domini generici, usato per verificare se il modello riconosce quando una query è estranea e rifiuta di rispondere invece di allucinare.

- **`03 Scaling` (Stress-Test di Sistema)**:  
  Non è un test di comprensione linguistica, ma uno **stress-test architetturale**. Misura come degradano latenza, consumi di token e aderenza alla grammatica JSON quando si impacchettano 1, 2, 4, 8, 16 e 32 domande parallele nello stesso prompt. Non esiste un "dataset accademico" per questo: si usa un banco controllato di 32 domande graduate (`scaling_question_bank()`).

- **`04 Workflow` e `05 Agent` (Business Policy Ibride)**:  
  Valutano l'interazione tra un LLM e il codice deterministico Python applicativo:
  - *04 Workflow*: simula una policy di **approvazione note spese aziendali** (il modello analizza congruità e frode, Python applica le regole di soglia `se importo > €100 e frode < 0.5 -> approva, altrimenti manager_review`).
  - *05 Agent*: simula una policy di **escalation supporto clienti** (se utente arrabbiato o richiede esplicitamente umano $\rightarrow$ *handoff*; se guasto urgente $\rightarrow$ *priority_support*).  
  Le policy aziendali e i grafi decisionali sono logiche applicative proprietarie di business, non dataset pubblici aperti.

---

### I Due Tier di Esecuzione

1. **Smoke Tier (`--dataset smoke`)**:
   - Esegue casi controllati in circa **10-30 secondi per modello**.
   - Ottimo per testare rapidamente tutti e 5 gli esperimenti (`routing`, `calibration`, `scaling`, `workflow`, `agent`) o per validare un nuovo modello/quantizzazione.
2. **Public Benchmark Tier (`--dataset public --profile budget`)**:
   - Esegue la valutazione scientifica rigorosa su larga scala per **`routing`** (77 classi) e **`calibration`** (in-scope + OOS).

---

## 3. Esecuzione per Singolo Modello

Tutti i comandi vanno eseguiti dalla cartella root del benchmark:
```bash
cd /Users/moltisantid/Personal/experiments/experiments/jev-vs-llm
```

### Modello 1: `nemotron-nano-4b` (NVIDIA 4B Q4)

```bash
# 1.1 Smoke Test completo (Tutti i 5 esperimenti - circa 1 minuto)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b \
  --experiments all \
  --dataset smoke

# 1.2 Benchmark Pubblico Reale (Routing 77 classi + Calibrazione OOS)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b \
  --experiments all \
  --dataset public \
  --profile budget

# 1.3 Solo Routing su Dataset Pubblico (BANKING77 - 77 casi)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b \
  --experiments routing \
  --dataset public \
  --profile budget

# 1.4 Solo Calibrazione su Dataset Pubblico (BANKING77 + CLINC150)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b \
  --experiments calibration \
  --dataset public \
  --profile budget
```

---

### Modello 2: `nemotron-nano-4b-q8` (NVIDIA 4B Q8 Alta Precisione)

```bash
# 2.1 Smoke Test completo (Tutti i 5 esperimenti)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q8 \
  --experiments all \
  --dataset smoke

# 2.2 Benchmark Pubblico Reale (Routing 77 classi + Calibrazione OOS)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q8 \
  --experiments all \
  --dataset public \
  --profile budget

# 2.3 Solo Routing su Dataset Pubblico (BANKING77)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q8 \
  --experiments routing \
  --dataset public \
  --profile budget
```

---

### Modello 3: `qwen3.5-9b-q4km` (Qwen 3.5 9B Q4)

```bash
# 3.1 Smoke Test completo (Tutti i 5 esperimenti - circa 2 minuti)
uv run python scripts/run_local_matrix.py \
  --models qwen3.5-9b-q4km \
  --experiments all \
  --dataset smoke

# 3.2 Benchmark Pubblico Reale (Routing 77 classi + Calibrazione OOS)
uv run python scripts/run_local_matrix.py \
  --models qwen3.5-9b-q4km \
  --experiments all \
  --dataset public \
  --profile budget

# 3.3 Solo Routing su Dataset Pubblico (BANKING77)
uv run python scripts/run_local_matrix.py \
  --models qwen3.5-9b-q4km \
  --experiments routing \
  --dataset public \
  --profile budget
```

---

### Modello 4: `qwen3.5-2b-q4km` (Qwen 3.5 2B Q4 Ultraleggero)

```bash
# 4.1 Smoke Test completo (Tutti i 5 esperimenti - circa 40 secondi)
uv run python scripts/run_local_matrix.py \
  --models qwen3.5-2b-q4km \
  --experiments all \
  --dataset smoke

# 4.2 Benchmark Pubblico Reale (Routing 77 classi + Calibrazione OOS)
uv run python scripts/run_local_matrix.py \
  --models qwen3.5-2b-q4km \
  --experiments all \
  --dataset public \
  --profile budget

# 4.3 Solo Routing su Dataset Pubblico (BANKING77)
uv run python scripts/run_local_matrix.py \
  --models qwen3.5-2b-q4km \
  --experiments routing \
  --dataset public \
  --profile budget
```

---

## 4. Esecuzione Batch Sequenziale (Tutti i 4 Modelli in Fila)

L'orchestratore attiva i modelli **uno alla volta**, gestendo automaticamente lo switch della memoria GPU/RAM e il ciclo di vita del server:

### A. Tutti i 4 modelli su Smoke Test Completo
Valuta tutti i 4 modelli sui 5 esperimenti sintetici:
```bash
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b,nemotron-nano-4b-q8,qwen3.5-9b-q4km,qwen3.5-2b-q4km \
  --experiments all \
  --dataset smoke
```

### B. Tutti i 4 modelli sul Benchmark Pubblico di Routing (BANKING77)
Esegue la matrice comparativa su 77 intent reali:
```bash
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b,nemotron-nano-4b-q8,qwen3.5-9b-q4km,qwen3.5-2b-q4km \
  --experiments routing \
  --dataset public \
  --profile budget
```

### C. Tutti i 4 modelli sul Benchmark Pubblico Completo (Routing + Calibration)
Esecuzione completa approfondita:
```bash
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b,nemotron-nano-4b-q8,qwen3.5-9b-q4km,qwen3.5-2b-q4km \
  --experiments all \
  --dataset public \
  --profile budget
```

---

## 5. Modalità Interattiva e Opzioni Avanzate

### Selezione Interattiva da Menu CLI
Se vuoi selezionare al volo quali modelli eseguire con una scelta numerica a video:
```bash
uv run python scripts/run_local_matrix.py -i --experiments all --dataset smoke
```

### Elenco dei Modelli Registrati
Visualizza in ogni momento i modelli disponibili e i relativi percorsi GGUF:
```bash
uv run python scripts/run_local_matrix.py --list
```

### Mantenere il Server Korgis Attivo tra i Run
Di default Korgis si spegne al termine del benchmark per liberare RAM. Se vuoi mantenerlo attivo per lanciare più comandi consecutivi senza attendere il riavvio:
```bash
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b \
  --experiments routing \
  --keep-korgis
```

---

## 6. Consultazione e Analisi dei Risultati

Al termine di ogni run i risultati vengono salvati automaticamente e aggregati in modo cumulativo:

1. **Dashboard HTML Interattivo**:
   Apri il report grafico nel browser:
   ```bash
   open results/local_report.html
   ```
   Contiene grafici di accuratezza, tasso di validità del JSON, distribuzione delle latenze per caso e percentili.

2. **Dati Grezzi Tabellari (CSV)**:
   Tutti i singoli campioni con prompt, token consumati, latenza esatta ed esito:
   ```text
   results/raw/local_results.csv
   ```

3. **Log del Server Locale Korgis / llama-server**:
   Se vuoi analizzare il throughput di token al secondo o i dettagli di inferenza:
   ```bash
   tail -f results/logs/korgis.log
   ```
