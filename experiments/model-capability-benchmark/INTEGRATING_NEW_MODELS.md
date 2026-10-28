# Guide: Integrating and Benchmarking a New Model

This guide documents the end-to-end, standard operating procedure for onboarding any new local LLM (GGUF / MLX) into **Korgis** and running it deterministically on the **Model Capability Benchmark (MCB)** suite, updating DuckDB analytics and the Decision Dashboard.

---

## Architecture & Pipeline Overview

```
┌─────────────────────────────────┐
│  Local Model Artifact           │  ~/.lmstudio/models/<publisher>/<repo>/<model>.gguf
│  (GGUF / MLX)                   │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│  Korgis Engine                  │  korgis/src/local_llm_server/models_registry.yaml
│  (Local LLM Server / Backend)   │  Resolves llama-server (Homebrew / LM Studio backend)
└────────────────┬────────────────┘
                 │ OpenAI-Compatible API (http://127.0.0.1:1235/v1)
                 ▼
┌─────────────────────────────────┐
│  Model Capability Benchmark     │  experiments/model-capability-benchmark/models.yaml
│  (MCB Unified Runner)           │  Profiles: smoke, core, challenge, comprehensive
└────────────────┬────────────────┘
                 │ Runs artifacts (.json, .jsonl, .html)
                 ▼
┌─────────────────────────────────┐
│  Analytics & Decision Dashboard │  DuckDB (benchmark.duckdb) -> published JSON bundle
│  (DuckDB + Vite/React UI)       │  http://localhost:5173 / dashboard.html
└─────────────────────────────────┘
```

---

## Step 1: Inspect the Model Artifact

Before writing configuration, discover the model's exact metadata from the binary:

### 1.1 Locate and verify the file
```bash
ls -lh "/path/to/your/model.gguf"
stat -f "%z bytes" "/path/to/your/model.gguf"
shasum -a 256 "/path/to/your/model.gguf"
```

### 1.2 Inspect GGUF metadata
Run this quick Python script to extract architecture, context length, size label, and chat template:

```bash
python3 -c "
import struct

def inspect_gguf(path):
    with open(path, 'rb') as f:
        magic = f.read(4)
        if magic != b'GGUF':
            print('Not a valid GGUF file')
            return
        version, n_tensors, n_kv = struct.unpack('<IQQ', f.read(20))
        print(f'GGUF v{version}, tensors={n_tensors}, kv_pairs={n_kv}')
        
        def read_str():
            l = struct.unpack('<Q', f.read(8))[0]
            return f.read(l).decode('utf-8', errors='replace')
            
        def read_val(vtype):
            if vtype in (0, 1): return struct.unpack('<B' if vtype==0 else '<b', f.read(1))[0]
            if vtype in (2, 3): return struct.unpack('<H' if vtype==2 else '<h', f.read(2))[0]
            if vtype in (4, 5): return struct.unpack('<I' if vtype==4 else '<i', f.read(4))[0]
            if vtype == 6: return struct.unpack('<f', f.read(4))[0]
            if vtype == 7: return struct.unpack('<?', f.read(1))[0]
            if vtype == 8: return read_str()
            if vtype == 9:
                atype, count = struct.unpack('<IQ', f.read(12))
                return [read_val(atype) for _ in range(count)]
            if vtype in (10, 11): return struct.unpack('<Q' if vtype==10 else '<q', f.read(8))[0]
            if vtype == 12: return struct.unpack('<d', f.read(8))[0]

        targets = ['architecture', 'size_label', 'context_length', 'template', 'block_count']
        for _ in range(n_kv):
            k = read_str()
            vtype = struct.unpack('<I', f.read(4))[0]
            val = read_val(vtype)
            if any(t in k for t in targets):
                if 'template' in k:
                    print(f'{k} = [template length {len(val)}]')
                    print(f'  Tail: {repr(val[-120:])}')
                else:
                    print(f'{k} = {val}')

inspect_gguf('/path/to/your/model.gguf')
"
```

Key fields to check:
- **`general.architecture`**: determines engine compatibility (e.g. `llama`, `qwen2`, `spark2_5`, `lfm2.5`, `lfm3`).
- **`<arch>.context_length`**: maximum context size (e.g., 8192, 131072, 1048576).
- **`tokenizer.chat_template`**: check whether `<think>` tags or `enable_thinking` parameters are present.

---

## Step 2: Validate Engine Compatibility

Test whether the installed `llama-server` can load the model:

```bash
/opt/homebrew/bin/llama-cli -m "/path/to/your/model.gguf" -p "Hello" -n 1
```

- **If it loads and generates**: standard Homebrew `llama_server` is fully compatible.
- **If it errors with `unknown model architecture: '...'`**:
  Check if a newer LM Studio backend includes support:
  ```bash
  for bin in ~/.lmstudio/extensions/backends/llama.cpp-*/llama-server; do
      echo \"Testing $bin\"
      $bin -m \"/path/to/your/model.gguf\" --port 8999 -c 512 2>&1 | head -n 8
  done
  ```
  If an LM Studio backend supports it (e.g. build 2.65.1 for `lfm3`), you can point to it in `models_registry.yaml` via:
  ```yaml
  params:
    llama_server_bin: ~/.lmstudio/extensions/backends/llama.cpp-mac-arm64-apple-metal-advsimd-2.65.1/llama-server
    llama_server_min_build: 1
    llama_server_bin_env: CUSTOM_LLAMA_SERVER_BIN  # optional env override
  ```

---

## Step 3: Register in Korgis (`models_registry.yaml`)

Edit [`korgis/src/local_llm_server/models_registry.yaml`](file:///Users/moltisantid/Personal/experiments/korgis/src/local_llm_server/models_registry.yaml):

```yaml
  <model-key>:
    filename: "<Exact-Filename>.gguf"
    lmstudio_path: "<Publisher>/<Repo-Name>"
    model_id: "<Publisher>/<Model-Name>"
    quantization: "<Quant-Label>"       # e.g., Q4_K_M, UD-Q4_K_XL, Q8_0
    sha256: "<64-char-sha256-hash>"
    size_gb: <size_in_gb>              # e.g., 3.30
    backend: llama_server
    thinking_mode: switchable          # switchable | none | native
    params:
      ctx_size: 8192
      startup_timeout: 300
      max_concurrent_requests: 1
      default_temperature: 0.0
      enable_thinking: false           # false ensures clean JSON structured output
      show_thinking: false
      llama_server_min_build: 10828    # or build requirement
    tags: [local, open-weight, <arch>, local-benchmark, <size>b, <quant>]
```

### Validate Korgis registry:
```bash
cd /Users/moltisantid/Personal/experiments/korgis
./.venv/bin/pytest tests/test_registry_validation.py tests/test_llama_server_config.py
```

---

## Step 4: Register in Model Capability Benchmark (`models.yaml`)

Edit [`experiments/model-capability-benchmark/models.yaml`](file:///Users/moltisantid/Personal/experiments/experiments/model-capability-benchmark/models.yaml):

```yaml
  <model-key>:
    model_id: <Publisher>/<Model-Name>
    runtime_model_id: <model-key>
    runtime: korgis-local
    family: <family-name>              # e.g., spark-x2.6, lfm3, qwen3
    parameters_b: <param_count>        # e.g., 4.4, 1.7, 24
    artifact:
      format: gguf
      quantization: <Quant-Label>      # e.g., Q4_K_M, Q8_0, UD-Q4_K_XL
      size_bytes: <exact_byte_size>
      metadata:
        sha256: <64-char-sha256-hash>
        resolved_by: korgis-model-registry
    tags:
      - local
      - open-weight
      - <family-name>
      - <quant>
```

### Validate benchmark configuration:
```bash
cd /Users/moltisantid/Personal/experiments/experiments/model-capability-benchmark
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
./.venv/bin/model-bench validate-config --models "<model-key>"
```

Expected output:
```json
{
  "issues": [],
  "models": ["<model-key>"],
  "ok": true,
  "suite_id": "capability-core",
  "suite_version": "3"
}
```

---

## Step 5: Test Model Activation & Smoke Run

### 5.1 Activate model on running Korgis instance
If Korgis is already running on port 1235:
```bash
curl -s -X POST http://127.0.0.1:1235/api/v1/models/activate \
  -H "Content-Type: application/json" \
  -d '{"model": "<model-key>"}'
```

Verify health:
```bash
curl -s http://127.0.0.1:1235/health
```

### 5.2 Test direct inference
```bash
curl -s http://127.0.0.1:1235/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<model-key>",
    "messages": [
      {"role": "user", "content": "What is the capital of Italy? Respond with JSON: {\"capital\": \"...\"}"}
    ],
    "response_format": {"type": "json_object"},
    "temperature": 0.0,
    "max_tokens": 100
  }'
```

### 5.3 Execute MCB smoke benchmark
```bash
cd /Users/moltisantid/Personal/experiments/experiments/model-capability-benchmark
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"

./.venv/bin/model-bench run \
  --models "<model-key>" \
  --capabilities structured-output \
  --profile smoke \
  --run-group "<model-key>-smoke" \
  --output-dir results/scratch/<model-key>-smoke
```

---

## Step 6: Execute the Full Canonical Core Benchmark

When the smoke test passes cleanly, launch the canonical `core` benchmark:

```bash
cd /Users/moltisantid/Personal/experiments/experiments/model-capability-benchmark
export KORGIS_BASE_URL="http://127.0.0.1:1235/v1"
export BENCHMARK_TIMEOUT_SECONDS=180

./.venv/bin/model-bench run \
  --models "<model-key>" \
  --capabilities all \
  --profile core \
  --run-group "<model-key>-core"
```

> [!IMPORTANT]
> **Reasoning Models & Token Budgets**:
> For models that output internal chain-of-thought tokens on complex tasks (e.g. classification tasks with 77 enum categories like `banking77`):
> - Pass `--max-output-tokens 4096` to avoid truncating `<think>` before the JSON answer is emitted.
> - Set `export BENCHMARK_TIMEOUT_SECONDS=240` so the HTTP transport does not time out while the model generates 2500–4000 tokens on local hardware.
> - Pass `--max-consecutive-failures 0` to disable early abort if running a recovery batch of hard cases.

---

## Step 7: Recovery and Run Consolidation (If Needed)

If any cases failed or were truncated during the initial run:

1. **Re-run only the failed cases with increased token limits**:
```bash
./.venv/bin/model-bench run \
  --models "<model-key>" \
  --capabilities all \
  --profile core \
  --max-output-tokens 4096 \
  --max-consecutive-failures 0 \
  --rerun-errors-from results/runs/<original-run-id> \
  --run-group "<model-key>-core-recovery"
```

2. **Consolidate original and recovery runs deterministically**:
```bash
./.venv/bin/model-bench consolidate \
  --run-dir results/runs/<original-run-id> \
  --run-dir results/runs/<recovery-run-id> \
  --run-group "<model-key>-core" \
  --run-id "<model-key>-core-consolidated"
```

---

## Step 8: Project to DuckDB & Update the Dashboard

Once the benchmark (or consolidated run) finishes:

```bash
cd /Users/moltisantid/Personal/experiments/experiments/model-capability-benchmark

# 1. Project raw runs into analytical DuckDB
uv run model-bench project

# 2. Export precomputed decision dashboard JSON bundle
uv run model-bench dashboard-data

# 3. Build production dashboard bundle & standalone HTML
uv run model-bench dashboard-build
```

### Accessing the Results:
- **Dev Server**: `http://localhost:5173` (refresh tab with `Cmd + R` to pick up newly projected runs).
- **Standalone Single-File HTML**: [dashboard.html](file:///Users/moltisantid/Personal/experiments/experiments/model-capability-benchmark/results/analytics/dashboard.html).
- **Analytical DuckDB**: [benchmark.duckdb](file:///Users/moltisantid/Personal/experiments/experiments/model-capability-benchmark/results/analytics/benchmark.duckdb).

---

## Step 9: Document in `HOW_TO_USE.md`

Add a dedicated numbered section in [`HOW_TO_USE.md`](file:///Users/moltisantid/Personal/experiments/experiments/model-capability-benchmark/HOW_TO_USE.md) detailing the model, its origin, HuggingFace links, and copy-pasteable commands for reproduction.
