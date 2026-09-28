# Guida all'Esecuzione dei Benchmark con Modelli Locali

Questo documento raccoglie i comandi per eseguire i benchmark di `jev-vs-llm` sui modelli locali tramite Korgis e per confrontare **Decisio con Qwen3.5 2B e 4B**. Per Decisio vai direttamente alla [sezione 7](#7-decisio-con-qwen35-2b-e-4b).

---

## 1. I 4 Modelli Locali Selezionati

Tutti i modelli sono configurati in [`benchmark-models.yaml`](./benchmark-models.yaml) e puntano agli artifact GGUF scaricati in LM Studio:

| Identificativo Chiave | Modello Base | Quantizzazione | Dimensione | Uso Consigliato |
|---|---|---|---|---|
| **`nemotron-nano-4b-q4`** | NVIDIA Nemotron-3 Nano 4B | `Q4_K_M` | 2.5 GB | Baseline veloce, ottimo bilanciamento velocità/accuratezza |
| **`nemotron-nano-4b-q8`** | NVIDIA Nemotron-3 Nano 4B | `Q8_0` | 4.3 GB | Massima fedeltà e calibrazione sulla classe 4B |
| **`qwen3.5-9b-q4km`** | Qwen 3.5 9B | `Q4_K_M` | 5.6 GB | Modello ad alte prestazioni per compiti multi-classe complessi |
| **`qwen3.5-2b-q4km`** | Qwen 3.5 2B | `Q4_K_M` | 1.2 GB | Modello ultraleggero compatto |
| **`minicpm5-2b-q4km`** | OpenBMB MiniCPM5 2B | `Q4_K_M` | 1.5 GB | Modello compatto con supporto reasoning opzionale (disabilitato per JSON) |
| **`spark-x2.5-4b-q4km`** | Spark-X 2.5 4B | `Q4_K_M` | 2.4 GB | Modello compatto 4B con 1M context e reasoning nativo switchable |

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

### Approfondimento: Il Benchmark di Routing con BANKING77

Nel benchmark pubblico, **`routing` usa BANKING77** (PolyAI, *Casanueva et al., 2020*). È un dataset pubblico di **intent classification** nel dominio dell'assistenza bancaria: ogni esempio è una frase reale scritta da un utente e il modello deve capire **a quale dei 77 intenti predefiniti appartiene**.

#### Cosa significa "Routing" in questo contesto

In questo benchmark, **routing non significa network routing o instradamento di pacchetti di rete**. Significa **intent routing** per il supporto clienti e l'automazione aziendale:

```text
Messaggio utente (ticket / chat)
              ↓
Classificatore / Decision Engine (JEV o LLM)
              ↓
1 delle 77 destinazioni / intenti bancari
```

Esempi concettuali dal dataset:

```text
"I haven't received my new card yet"
        ↓
card_arrival

"I was charged twice for the same transaction"
        ↓
card_payment_fee_charged / wrong_amount_of_cash_received

"I forgot my PIN number"
        ↓
pin_blocked / change_pin
```

#### Perché BANKING77 è particolarmente interessante per il confronto JEV vs LLM

Non si tratta di una classificazione banale a 3 opzioni (es. `billing`, `technical_support`, `other`). È una sfida reale per diversi motivi:

1. **77 classi molto vicine semanticamente**: Moltissimi intenti hanno confini sfumati (ad esempio problematiche diverse legate alla carta: `card_arrival`, `card_delivery_estimate`, `card_not_working`, `card_linking`, `lost_or_stolen_card`, oppure pagamenti, bonifici, prelievi bancomat, tassi di cambio). Il modello non può cavarsela con semplici parole chiave.
2. **Spazio delle azioni strutturato e limitato**: In produzione i sistemi di assistenza automatica devono instradare le richieste verso workflow o dipartimenti ben definiti.
3. **Decision Engine (JEV) vs Generazione di Token (LLM)**: JEV espone la distribuzione di probabilità nativa su uno spazio di scelte discrete (`Choice`), mentre un LLM deve leggere tutte le 77 opzioni nel contesto e generare output JSON strutturato, testando robustezza grammaticale, consumo di token e latenza.
4. **Velocità e costi in scenari ad alto volume**: Il routing dei ticket è un'operazione che in produzione deve costare pochissimo ed essere istantanea (<100ms). Valutare modelli compatti locali e JEV su questo task mostra il vero trade-off economico rispetto a LLM cloud giganteschi.

#### Flusso di Valutazione e Metriche

```text
                    BANKING77
                         │
                         ▼
           "Testo della richiesta"
                         │
          ┌──────────────┴──────────────┐
          │                             │
         JEV                           LLM
          │                             │
          ▼                             ▼
   intent predetto               intent predetto
          │                             │
          └──────────────┬──────────────┘
                         ▼
              Ground Truth Ufficiale
```

Vengono misurate:
- **Accuracy** (con intervalli di confidenza di Wilson al 95%);
- **Macro-F1** (media non pesata su tutti i 77 intenti per non penalizzare classi rare);
- **Percentuale di JSON valido** (per verificare l'aderenza dello Structured Output dell'LLM);
- **Latenza client** (p50, p95, p99);
- **Costo stimato per richiesta**;
- **Coppie di confusione più frequenti** (per analizzare dove il modello sbaglia tra classi affini).

#### Quale parte del dataset usiamo

Nel repository usiamo **esclusivamente il test set ufficiale di BANKING77**:
- **3.080 esempi totali**
- **77 intenti** (in media circa 40 esempi per classe)
- **Zero label sintetiche**: la ground truth proviene al 100% dalle annotazioni umane originali di PolyAI.

I profili disponibili sono quattro:

| Profilo | Esempi Routing | Esempi per classe | In-Scope Calibration | OOS Calibration | Uso consigliato |
|---|---:|---:|---:|---:|---|
| `budget` | **77** | **1 per classe** | 40 | 40 | Sanity check velocissimo ed economico su tutte le 77 classi |
| `quick` | **154** | **2 per classe** | 100 | 100 | Test rapido di regressione / integrazione |
| `standard` | **770** | **10 per classe** | 500 | 500 | Benchmark comparativo standard bilanciato |
| `full` | **3.080** | **~40 per classe** | tutti | tutti | Valutazione esaustiva dell'intero test set |

Quando si usa un sottoinsieme (`budget`, `quick`, `standard`), il campionamento è **rigorosamente bilanciato per classe** (`class-balanced` con seed deterministico 42). Per esempio, `budget` estrae esattamente 1 esempio casuale ma fisso per ciascuna delle 77 classi, `quick` ne estrae 2, e `standard` 10 per classe.

#### Differenza fondamentale: `routing` vs `calibration`

È fondamentale non confondere **`routing`** con **`calibration`**:

- **`routing` è una Closed-Set Classification:**
  Al modello viene detto che la richiesta appartiene **sicuramente** a una delle 77 categorie bancarie:
  ```text
  Query BANKING77
        ↓
  {intent_1, intent_2, ... intent_77}
        ↓
  Scegline esattamente una
  ```
  *In sintesi: misura quanto il modello è bravo a **scegliere la porta giusta tra 77 porte**.*

- **`calibration` è una Open-Set / Out-Of-Scope Detection:**
  In questo secondo test vengono mescolati esempi bancari in-scope con esempi **fuori dominio** presi dal dataset CLINC150, mappati sull'opzione esplicita `other`:
  ```text
  Query (Bancaria oppure OOS)
        ↓
  {intent_1, intent_2, ... intent_77} + "other"
        ↓
  Classifica nell'intent bancario oppure scarta come "other"
  ```
  *In sintesi: misura se il modello **sa accorgersi quando nessuna porta è quella giusta**, facendo crollare la propria confidenza o rifiutando la risposta.*

---

## 3. Esecuzione per Singolo Modello

Tutti i comandi vanno eseguiti dalla cartella root del benchmark:
```bash
cd /Users/moltisantid/Personal/experiments/experiments/jev-vs-llm
```

### Modello 1: `nemotron-nano-4b-q4` (NVIDIA 4B Q4)

```bash
# 1.1 Smoke Test completo (Tutti i 5 esperimenti - circa 1 minuto)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q4 \
  --experiments all \
  --dataset smoke

# 1.2 Benchmark Pubblico Reale (Routing 77 classi + Calibrazione OOS)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q4 \
  --experiments all \
  --dataset public \
  --profile budget

# 1.3 Solo Routing su Dataset Pubblico (BANKING77 - 77 casi)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q4 \
  --experiments routing \
  --dataset public \
  --profile budget

# 1.4 Solo Calibrazione su Dataset Pubblico (BANKING77 + CLINC150)
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q4 \
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

### Modello 5: `minicpm5-2b-q4km` (OpenBMB MiniCPM5 2B Q4)

```bash
# 5.1 Smoke Test completo (Tutti i 5 esperimenti - circa 40 secondi)
uv run python scripts/run_local_matrix.py \
  --models minicpm5-2b-q4km \
  --experiments all \
  --dataset smoke

# 5.2 Benchmark Pubblico Reale (Routing 77 classi + Calibrazione OOS)
uv run python scripts/run_local_matrix.py \
  --models minicpm5-2b-q4km \
  --experiments all \
  --dataset public \
  --profile budget

# 5.3 Solo Routing su Dataset Pubblico (BANKING77)
uv run python scripts/run_local_matrix.py \
  --models minicpm5-2b-q4km \
  --experiments routing \
  --dataset public \
  --profile budget
```

---

### Modello 6: `spark-x2.5-4b-q4km` (Spark-X 2.5 4B Q4)

```bash
# 6.1 Smoke Test completo (Tutti i 5 esperimenti - circa 40 secondi)
uv run python scripts/run_local_matrix.py \
  --models spark-x2.5-4b-q4km \
  --experiments all \
  --dataset smoke

# 6.2 Benchmark Pubblico Reale (Routing 77 classi + Calibrazione OOS in modalità budget)
uv run python scripts/run_local_matrix.py \
  --models spark-x2.5-4b-q4km \
  --experiments all \
  --dataset public \
  --profile budget

# 6.3 Solo Routing su Dataset Pubblico (BANKING77 - 77 casi budget)
uv run python scripts/run_local_matrix.py \
  --models spark-x2.5-4b-q4km \
  --experiments routing \
  --dataset public \
  --profile budget

# 6.4 Solo Calibrazione su Dataset Pubblico (BANKING77 + CLINC150 budget)
uv run python scripts/run_local_matrix.py \
  --models spark-x2.5-4b-q4km \
  --experiments calibration \
  --dataset public \
  --profile budget
```

---

## 4. Esecuzione Batch Sequenziale

L'orchestratore attiva i modelli **uno alla volta**, gestendo automaticamente lo switch della memoria GPU/RAM e il ciclo di vita del server:

### A. Tutti i 4 modelli su Smoke Test Completo
Valuta tutti i 4 modelli sui 5 esperimenti sintetici:
```bash
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q4,nemotron-nano-4b-q8,qwen3.5-9b-q4km,qwen3.5-2b-q4km,minicpm5-2b-q4km \
  --experiments all \
  --dataset smoke
```

### B. Tutti i modelli sul Benchmark Pubblico di Routing (BANKING77)
Esegue la matrice comparativa su 77 intent reali:
```bash
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q4,nemotron-nano-4b-q8,qwen3.5-9b-q4km,qwen3.5-2b-q4km,minicpm5-2b-q4km \
  --experiments routing \
  --dataset public \
  --profile budget
```

### C. Tutti i modelli sul Benchmark Pubblico Completo (Routing + Calibration)
Esecuzione completa approfondita:
```bash
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q4,nemotron-nano-4b-q8,qwen3.5-9b-q4km,qwen3.5-2b-q4km,minicpm5-2b-q4km \
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
  --models nemotron-nano-4b-q4 \
  --experiments routing \
  --keep-korgis
```

### Abilitare il Thinking / Reasoning Mode (`--thinking`)
Per i modelli che supportano tracce di ragionamento (es. `nemotron-nano-4b-q4`, `nemotron-nano-4b-q8`, `minicpm5-2b-q4km`):
```bash
# Esecuzione con thinking attivo da riga di comando:
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q4 \
  --experiments routing \
  --thinking

# Benchmark pubblico reale BANKING77 con thinking:
uv run python scripts/run_local_matrix.py \
  --models nemotron-nano-4b-q4 \
  --experiments routing \
  --dataset public \
  --profile budget \
  --thinking
```
> [!TIP]
> Puoi anche abilitare il thinking come predefinito per tutte le esecuzioni modificando `enable_thinking: true` nel file [`experiments_config.yaml`](experiments_config.yaml). Il sistema adatterà automaticamente il limite dei token di output a 2048 token per permettere la generazione completa della traccia `<think>` prima del JSON.

---

## 6. Consultazione e Analisi dei Risultati

Al termine di ogni run Korgis o Decisio i risultati vengono salvati automaticamente e aggregati in modo cumulativo e **strutturale**. Decisio conserva anche gli artifact dettagliati descritti nella sezione 7; i metodi `semantic` e `json` appaiono nella dashboard come configurazioni separate.

1. **Accorpamento Strutturale Solido a 4 Dimensioni**:
   L'aggregazione non sovrascrive né disperde i risultati precedenti. Ogni esecuzione è identificata univocamente da:
   $$\text{Key} = (\text{Modello}, \text{Dataset}, \text{Configurazione}, \text{Task})$$
   Questo garantisce che per ciascuna combinazione (es. *Nemotron Nano 4B Q4 con Thinking ON* vs *Thinking OFF*, oppure su *Banking77* vs *Smoke*) vengano sempre mantenuti e visualizzati gli **ultimi risultati validi**.

2. **Filtro per Dataset Tier nella Dashboard UI**:
   Nella barra superiore della Dashboard è possibile filtrare i risultati con un click:
   - **`Public Benchmark (Banking77)`**: Mostra solo i run condotti sul dataset pubblico standard a 77 classi per un confronto equo e rigoroso ad armi pari.
   - **`Smoke Test Suite (24 casi)`**: Mostra i risultati rapidi sui casi sintetici locali (ottimo per confrontare l'impatto immediato di parametri come il thinking on/off).
   - **`All Runs`**: Visualizza la matrice completa di tutti i modelli e le configurazioni testate.

3. **Dashboard HTML Interattivo**:
   Apri il report grafico nel browser:
   ```bash
   open results/local_report.html
   ```
   Oppure visualizza la UI reattiva di sviluppo (se il dev server è avviato):
   ```bash
   npm --prefix dashboard run dev
   ```

4. **Dati Grezzi Tabellari (CSV)**:
   Tutti i singoli campioni con prompt, token consumati, latenza esatta ed esito:
   ```text
   results/raw/local_results.csv
   ```

5. **Log del Server Locale Korgis / llama-server**:
   Se vuoi analizzare il throughput di token al secondo o i dettagli di inferenza:
   ```bash
   tail -f results/logs/korgis.log
   ```

---

## 7. Decisio con Qwen3.5 2B e 4B

Usa lo stesso launcher degli altri benchmark, aggiungendo **`--provider decisio`**. Legge i GGUF da `benchmark-models.yaml`, esegue un modello alla volta e mostra lo stesso stile di progress con Rich: intestazione per modello, barra per metodo, casi completati/totali, tempo trascorso, ETA, accuratezza e latenza. Durante caricamento e warmup mostra uno spinner con la fase corrente; il warmup non conta tra i casi misurati. L'ETA compare quando sono disponibili tempi dei nuovi casi, anche nei run ripresi.

### Comando consigliato: come gli altri run

Dalla cartella del benchmark, con l'ambiente Decisio già preparato:

```bash
cd /Users/moltisantid/Personal/experiments/experiments/jev-vs-llm

# BANKING77: Qwen 2B e 4B in sequenza, 77 casi per modello
uv run python scripts/run_local_matrix.py \
  --provider decisio \
  --models qwen3.5-2b-q4km,qwen3.5-4b-q4km \
  --experiments routing \
  --dataset public \
  --profile budget

# Smoke: stessi 24 casi a 6 classi per entrambi i modelli
uv run python scripts/run_local_matrix.py \
  --provider decisio \
  --models qwen3.5-2b-q4km,qwen3.5-4b-q4km \
  --experiments routing \
  --dataset smoke
```

Non servono le variabili `DECISIO_*`: nel layout locale il launcher trova il checkout adiacente `/Users/moltisantid/Personal/decisio` e il suo `.venv/bin/python`. Su altre macchine usa `--decisio-root /percorso/decisio` ed eventualmente `--decisio-python /percorso/python`. Rich e l'interfaccia girano nell'ambiente del benchmark; l'inferenza usa l'ambiente separato di Decisio.

I metodi predefiniti sono `direct,json` per smoke e `semantic,json` per public. `--methods direct,fresh,json` aggiunge il controllo senza riuso allo smoke. `--profile quick`, `standard` e `full` selezionano rispettivamente 154, 770 e tutti i 3.080 casi pubblici; `--cases N` permette una prova ridotta. `--threads` vale 4 di default. Decisio esegue solo routing: `--experiments all` indica tutti gli esperimenti attualmente supportati, quindi solo routing.

Ogni nuova esecuzione crea una cartella univoca sotto `results/decisio/` e stampa subito il percorso e il comando per riprenderla. Un eventuale `--output percorso` deve indicare una cartella nuova. Per riprendere una matrice interrotta basta:

```bash
uv run python scripts/run_local_matrix.py \
  --provider decisio \
  --resume results/decisio/NOME-DELLA-SESSIONE
```

Puoi riprendere anche il vecchio run 2B già creato con `compare_decisio.py`, con la nuova interfaccia:

```bash
uv run python scripts/run_local_matrix.py \
  --provider decisio \
  --resume results/decisio/20260923-184748/2b-banking77
```

La ripresa recupera modelli, dataset, casi, metodi e thread salvati; salta i casi già presenti e i metodi completi. `Ctrl+C` ferma il processo di inferenza avviato dal launcher e conserva i casi completati. Per vedere i modelli predefiniti usa `--provider decisio --list`. Le barre si attivano automaticamente nel terminale; `--no-progress` o `BENCHMARK_NO_PROGRESS=1` producono log testuali con fase e avanzamento per caso. `--progress` forza le barre.

Al termine appare una tabella comparativa con accuracy, macro-F1 e latenza p50/p95. Nella cartella di sessione trovi `matrix.json` e una sottocartella per modello con `summary.json`, `rows.jsonl`, `fixture.json` e `manifest.json`. Il runner importa inoltre le righe nel CSV cumulativo e rigenera la dashboard, mantenendo distinti metodo e device (`semantic-metal`, `json-metal`, oppure le varianti CPU). Su macOS il runner usa Metal per default; passa `--device cpu` per il riferimento CPU.

Il launcher usa [`scripts/compare_decisio.py`](scripts/compare_decisio.py) come worker nativo. Le sezioni seguenti documentano anche l'invocazione avanzata del singolo worker; per l'uso quotidiano usa i comandi qui sopra.

### 7.1 Preparazione

Nel checkout locale di Decisio è già presente l'ambiente con `llama-cpp-python==0.3.35`. Su una nuova installazione preparalo una volta:

```bash
cd /Users/moltisantid/Personal/decisio
uv sync --frozen --extra llama
```

Poi imposta i percorsi nella stessa shell in cui eseguirai i benchmark:

```bash
cd /Users/moltisantid/Personal/experiments/experiments/jev-vs-llm

DECISIO_ROOT=/Users/moltisantid/Personal/decisio
DECISIO_PYTHON="$DECISIO_ROOT/.venv/bin/python"
DECISIO_QWEN2="$HOME/.lmstudio/models/unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q4_K_M.gguf"
DECISIO_QWEN4="$HOME/.lmstudio/models/unsloth/Qwen3.5-4B-GGUF/Qwen3.5-4B-Q4_K_M.gguf"
DECISIO_RUN="results/decisio/$(date +%Y%m%d-%H%M%S)"

"$DECISIO_PYTHON" scripts/compare_decisio.py --help
```

I pesi devono essere già scaricati. Il runner usa il backend **CPU di riferimento**, quattro thread e thinking disabilitato. Esegui i due modelli in sequenza e senza altri benchmark concorrenti, per mantenere le latenze confrontabili.

### 7.2 Primo confronto: 24 casi, 6 classi

Esegui entrambi i comandi, uno dopo l'altro:

```bash
# Qwen3.5 2B: Decisio diretto, controllo senza riuso, baseline JSON
"$DECISIO_PYTHON" scripts/compare_decisio.py \
  --decisio-root "$DECISIO_ROOT" \
  --model "$DECISIO_QWEN2" \
  --dataset smoke \
  --methods direct,fresh,json \
  --threads 4 \
  --output "$DECISIO_RUN/2b-smoke"

# Qwen3.5 4B: stessi casi e impostazioni
"$DECISIO_PYTHON" scripts/compare_decisio.py \
  --decisio-root "$DECISIO_ROOT" \
  --model "$DECISIO_QWEN4" \
  --dataset smoke \
  --methods direct,fresh,json \
  --threads 4 \
  --output "$DECISIO_RUN/4b-smoke"
```

Ogni metodo effettua un warmup escluso dalle misure, seguito dagli stessi 24 casi in ordine deterministico (seed 42). Con tre metodi sono **72 classificazioni misurate per modello**. Caricamento e hash del GGUF sono esclusi dalla latenza per richiesta.

| `--methods` | Comportamento | Uso |
|---|---|---|
| `direct` | Legge i logits delle lettere A/B/C, con riuso del prefisso abilitato | Classificazione nativa, zero token di risposta |
| `fresh` | Stesso prompt di `direct`, senza esecuzione con prefisso condiviso | Controllo di equivalenza |
| `json` | Genera `{"choice":"classe"}`, massimo 64 token | Baseline generativa sullo stesso backend CPU |
| `semantic` | Valuta ogni candidato rispetto alle alternative tramite logits Yes/No | Scorer sperimentale, supporta anche 77 classi |

Per una verifica rapida aggiungi `--cases 3` e usa una nuova directory di output. Quel sottoinsieme smoke non è bilanciato per classe e non sostituisce il confronto completo. Per il solo Decisio usa `--methods direct`; per confrontarlo con JSON usa `--methods direct,json`.

### 7.3 BANKING77: scorer semantico su tutte le 77 classi

**Il percorso diretto nativo supporta al massimo 26 classi.** Il runner rifiuta `--dataset banking77 --methods direct` o `fresh`. Per BANKING77 puoi usare `semantic,json`: non riduce le classi, ma esegue 77 valutazioni di candidato per ogni richiesta semantica ed è quindi molto più costoso del percorso diretto. È un esperimento distinto, non una misura delle prestazioni di `direct` su BANKING77.

Prepara prima i dataset pubblici con l'ambiente del benchmark:

```bash
uv run jev-bench prepare-data
```

Esegui il profilo da 77 esempi, uno per classe, con seed 42:

```bash
"$DECISIO_PYTHON" scripts/compare_decisio.py \
  --decisio-root "$DECISIO_ROOT" \
  --model "$DECISIO_QWEN2" \
  --dataset banking77 \
  --cases 77 \
  --methods semantic,json \
  --threads 4 \
  --output "$DECISIO_RUN/2b-banking77"

"$DECISIO_PYTHON" scripts/compare_decisio.py \
  --decisio-root "$DECISIO_ROOT" \
  --model "$DECISIO_QWEN4" \
  --dataset banking77 \
  --cases 77 \
  --methods semantic,json \
  --threads 4 \
  --output "$DECISIO_RUN/4b-banking77"
```

Questo runner usa `--dataset banking77` e `--cases`, anziché i flag `--dataset public --profile budget` di Korgis. Per campioni più grandi imposta `--cases 154` o `--cases 770`; omettendo `--cases` valuta tutti i 3.080 esempi. Il comando pubblico è disponibile, ma non è stato incluso nel primo confronto smoke.

### 7.4 Dove leggere i risultati

Il launcher mostra barre e riepilogo nel terminale; l'invocazione diretta di `compare_decisio.py` mostra log testuali. Ogni directory del singolo modello contiene:

| File | Contenuto |
|---|---|
| `summary.json` | Accuracy, macro-F1, validità, latenza p50/p95, token generati, cache hit e casi errati, per metodo |
| `rows.jsonl` | Singole predizioni, ground truth, distribuzioni/punteggi, latenza, contatori runtime ed eventuali errori |
| `fixture.json` | Testi, etichette attese, domanda e classi usate |
| `manifest.json` | Revisione/stato Decisio, hash GGUF e dataset selezionato, backend e parametri runtime |

```bash
"$DECISIO_PYTHON" -m json.tool "$DECISIO_RUN/2b-smoke/summary.json"
"$DECISIO_PYTHON" -m json.tool "$DECISIO_RUN/4b-smoke/summary.json"
```

Le directory devono essere nuove: il runner rifiuta di sovrascrivere risultati esistenti. Rigenera `DECISIO_RUN` per ripetere una sessione. Gli artifact sono locali e gitignored; al completamento il runner aggiorna automaticamente la dashboard condivisa.

Se un run è stato interrotto dopo la creazione della directory, rilancia **lo stesso comando** aggiungendo `--resume`. Il runner controlla fixture, modello e relativo hash, metodi, dataset e numero di thread; conserva le righe già complete e prosegue dal primo caso mancante:

```bash
"$DECISIO_PYTHON" scripts/compare_decisio.py \
  --decisio-root "$DECISIO_ROOT" \
  --model "$DECISIO_QWEN2" \
  --dataset banking77 \
  --cases 77 \
  --methods semantic,json \
  --threads 4 \
  --output "$DECISIO_RUN/2b-banking77" \
  --resume
```

Senza `--resume`, una directory esistente viene rifiutata intenzionalmente per evitare la perdita accidentale dei risultati precedenti.

Nel leggere il confronto:

- Accuratezza e macro-F1 includono nel denominatore anche output invalidi ed errori.
- I punteggi nativi sono preferenze condizionate alle classi, **non confidenze calibrate**.
- Sui prompt brevi smoke il backend può registrare zero cache hit: il checkpoint richiede blocchi completi da 512 token. Non attribuire alla cache un miglioramento senza riuso misurato.
- Le latenze CPU non sono direttamente confrontabili con precedenti run Korgis su GPU/Metal o con API remote.
- I 24 casi smoke verificano il funzionamento e danno un primo confronto; non dimostrano la qualità su BANKING77.

Protocollo e dettagli tecnici: [`DECISIO.md`](DECISIO.md).

### 7.5 Primo confronto eseguito — 23 settembre 2026

Risultati sui **24 casi smoke a 6 classi**, Q4_K_M, CPU con quattro thread:

| Modello | Metodo | Corretti | Macro-F1 | Latenza p50 | Latenza p95 |
|---|---|---:|---:|---:|---:|
| Qwen3.5 2B | Decisio `direct` | 22/24 (91,7%) | 0,919 | 1,253 s | 1,452 s |
| Qwen3.5 2B | Baseline `json` | 23/24 (95,8%) | 0,958 | 1,480 s | 1,688 s |
| Qwen3.5 4B | Decisio `direct` | 24/24 (100%) | 1,000 | 3,097 s | 3,733 s |
| Qwen3.5 4B | Baseline `json` | 23/24 (95,8%) | 0,958 | 3,550 s | 3,922 s |

Tutti i 144 output misurati sono validi, includendo i controlli `fresh`. Per entrambi i modelli `direct` e `fresh` restituiscono punteggi identici su ogni caso; i cache hit sono zero. È un singolo passaggio per metodo su un campione piccolo, senza evidenza sufficiente per concludere superiorità generale o speedup statisticamente stabile.

Artifact locali: [`2B summary`](results/decisio/2b-smoke-v2/summary.json), [`4B summary`](results/decisio/4b-smoke/summary.json). Nelle stesse directory trovi fixture, manifest e righe grezze. Revisione Decisio: `1a8507178a6909a8270ef63303270ce36bd85f68`. BANKING77 non è stato eseguito in questa sessione.
