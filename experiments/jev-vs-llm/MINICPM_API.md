# MiniCPM API setup

MiniCPM is benchmarked as a **remote API provider**, not as a Korgis/GGUF local model.

The official MiniCPM API is OpenAI-compatible:

```text
Base URL: https://api.modelbest.cn/v1
Chat endpoint: /chat/completions
Authentication: Authorization: Bearer <API_KEY>
```

Official API reference:

```text
https://github.com/OpenBMB/MiniCPM-V/blob/main/docs/api.md
```

## 1. Configure credentials

Create `.env` from the example file and set:

```bash
export MINICPM_API_KEY="..."
export MINICPM_BASE_URL="https://api.modelbest.cn/v1"
export MINICPM_MODEL="MiniCPM-V-4.6-1B"
export MINICPM_MAX_OUTPUT_TOKENS=2048
```

Never commit the real API key.

The default benchmark model is `MiniCPM-V-4.6-1B` because it is an explicitly versioned model exposed by the current official API and accepts text-only requests. The benchmark does not claim that this is a 4B model.

## 2. Smoke-test the API directly

```bash
curl https://api.modelbest.cn/v1/chat/completions \
  -H "Authorization: Bearer $MINICPM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "MiniCPM-V-4.6-1B",
    "messages": [
      {
        "role": "user",
        "content": "Reply with JSON only: {\"ok\": true}"
      }
    ]
  }'
```

## 3. Run one benchmark experiment

```bash
uv run jev-bench experiment routing \
  --provider minicpm \
  --model MiniCPM-V-4.6-1B
```

Public BANKING77 routing:

```bash
uv run jev-bench experiment routing \
  --provider minicpm \
  --model MiniCPM-V-4.6-1B \
  --dataset public \
  --profile budget
```

## 4. Include MiniCPM in the public comparison

```bash
uv run jev-bench compare-public \
  --profile budget \
  --models gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol \
  --include-minicpm \
  --minicpm-model MiniCPM-V-4.6-1B
```

MiniCPM then shares the same run group, public cases and result schema as Jev and the GPT baselines.

## 5. What the adapter measures

The adapter records:

- model ID;
- end-to-end request latency;
- prompt/input tokens when reported by the API;
- completion/output tokens when reported by the API;
- selected answer;
- self-reported confidence;
- selected-answer probability;
- output-validity failures and provider errors.

The benchmark asks MiniCPM for compact JSON only. It does not use vision/audio/video inputs.

## 6. Cost handling

Do not hard-code a MiniCPM token price unless an authoritative pricing source has been captured in `pricing_snapshot.json`.

When the selected MiniCPM API model has no price entry in the committed snapshot, `estimated_cost_usd` is recorded as unknown (`None`) rather than falsely reporting zero.

This is different from Korgis local inference, where provider API fee is intentionally recorded as zero while hardware/energy cost remains outside the benchmark.

## 7. Why there is no `minicpm3-4b-q4km` default

The previous benchmark configuration assumed a Korgis registry key named `minicpm3-4b-q4km`.

That key is not part of Korgis' built-in registry, so commands such as:

```bash
local-llm download minicpm3-4b-q4km
```

must not appear as a default setup path.

MiniCPM3-4B exists as an upstream checkpoint, but that does not imply that a particular GGUF/Q4 artifact is an official Korgis model or that Korgis knows how to download it.

The official API baseline and any future self-hosted MiniCPM experiment must be treated as two different benchmark configurations.
