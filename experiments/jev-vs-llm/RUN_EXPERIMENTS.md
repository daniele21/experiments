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

## 2. Panoramica degli Esperimenti

La suite supporta due tier di dataset:

### A. Smoke Tier (`--dataset smoke`)
Test rapido (10-30 secondi per modello) con casi sintetici per verificare il corretto funzionamento end-to-end:
- **`routing`** (01): Classificazione ticket su 6 reparti (billing, technical, sales, account, shipping, cancellation).
- **`calibration`** (02): Calibrazione delle probabilità e scarto out-of-scope.
- **`scaling`** (03): Scalabilità decisionale (1, 2, 4, 8, 16, 32 domande parallele).
- **`workflow`** (04): Policy a grafo ibrido (decisioni modello + regole deterministiche Python).
- **`agent`** (05): Agente di approvazione spese con escalation policy.

### B. Public Benchmark Tier (`--dataset public --profile budget`)
Valutazione su dataset pubblici reali e standard della letteratura scientifica:
- **`routing`** (`01-routing-public`): Classificazione su **BANKING77** (77 classi reali di intent bancari).
- **`calibration`** (`02-calibration-public`): Calibrazione e rilevamento out-of-scope su **BANKING77** (in-scope) e **CLINC150** (out-of-scope).

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
